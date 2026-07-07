import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.remediation import Remediation
from app.models.user import User
from app.models.vulnerability_finding import VulnerabilityFinding
from app.models.workflow_run import WorkflowRun

router = APIRouter()

_TREND_DAYS = 30

@router.get("/")
async def get_analytics(
    application_id: uuid.UUID | None = Query(default=None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # When an application is selected, every metric is scoped to its rows.
    wf_app = [WorkflowRun.application_id == application_id] if application_id else []
    rem_app = [Remediation.application_id == application_id] if application_id else []
    vuln_app = [VulnerabilityFinding.application_id == application_id] if application_id else []

    # Total = every ingested run (incl. in-progress / queued, which have NULL conclusion).
    total_runs = (
        await db.execute(select(func.count()).select_from(WorkflowRun).where(*wf_app))
    ).scalar_one() or 0

    # Completed = finished runs only (conclusion is set). All rate math uses THIS as the
    # denominator so in-progress / queued runs never dilute failure/success rates.
    completed_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion.is_not(None), *wf_app)
        )
    ).scalar_one() or 0

    failed_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion == "failure", *wf_app)
        )
    ).scalar_one() or 0

    success_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion == "success", *wf_app)
        )
    ).scalar_one() or 0

    other_runs = max(completed_runs - success_runs - failed_runs, 0)

    # Authoritative rates: over COMPLETED runs, not total.
    failure_rate = round(failed_runs / completed_runs, 4) if completed_runs else 0.0
    success_rate = round(success_runs / completed_runs, 4) if completed_runs else 0.0

    # Top failing repos.
    top_failing_result = await db.execute(
        select(WorkflowRun.repo_name, func.count().label("count"))
        .where(WorkflowRun.conclusion == "failure", *wf_app)
        .group_by(WorkflowRun.repo_name)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_failing_repos = [
        {"repo": row.repo_name, "count": row.count} for row in top_failing_result.all()
    ]

    # Top failing workflows.
    top_failing_wf_result = await db.execute(
        select(WorkflowRun.workflow_name, func.count().label("count"))
        .where(WorkflowRun.conclusion == "failure", *wf_app)
        .group_by(WorkflowRun.workflow_name)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_failing_workflows = [
        {"workflow": row.workflow_name, "count": row.count} for row in top_failing_wf_result.all()
    ]

    # 30-day run trend.
    since = datetime.now(timezone.utc) - timedelta(days=_TREND_DAYS)
    day = func.date(WorkflowRun.created_at)
    trend_result = await db.execute(
        select(
            day.label("date"),
            func.sum(case((WorkflowRun.conclusion == "success", 1), else_=0)).label("success"),
            func.sum(case((WorkflowRun.conclusion == "failure", 1), else_=0)).label("failed"),
        )
        .where(WorkflowRun.created_at >= since, *wf_app)
        .group_by(day)
        .order_by(day)
    )
    run_trend = [
        {"date": str(row.date), "success": int(row.success or 0), "failed": int(row.failed or 0)}
        for row in trend_result.all()
    ]

    # Run frequency: completed runs/day over the trend window (DORA "deployment frequency" proxy).
    completed_in_window = (
        await db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.conclusion.is_not(None), WorkflowRun.created_at >= since, *wf_app)
        )
    ).scalar_one() or 0
    runs_per_day = round(completed_in_window / _TREND_DAYS, 2)

    # A raised PR = a remediation that actually produced a PR URL (not merely "helpful").
    remediations_raised = (
        await db.execute(
            select(func.count()).select_from(Remediation).where(Remediation.pr_url.is_not(None), *rem_app)
        )
    ).scalar_one() or 0

    # Avg analysis time (failure ingested -> analysis done).
    epoch = func.extract("epoch", Remediation.updated_at - Remediation.created_at)
    avg_analysis_seconds = (
        await db.execute(
            select(func.avg(epoch)).where(
                Remediation.status.in_(["analyzed", "pr_raised", "helpful"]), *rem_app
            )
        )
    ).scalar_one()
    avg_analysis_seconds = round(float(avg_analysis_seconds)) if avg_analysis_seconds is not None else None

    # Legacy: time-to-PR measured from remediation row creation.
    epoch_pr = func.extract("epoch", Remediation.pr_raised_at - Remediation.created_at)
    avg_time_to_pr_seconds = (
        await db.execute(
            select(func.avg(epoch_pr)).where(Remediation.pr_raised_at.is_not(None), *rem_app)
        )
    ).scalar_one()
    avg_time_to_pr_seconds = round(float(avg_time_to_pr_seconds)) if avg_time_to_pr_seconds is not None else None

    # MTTR (Mean Time To Remediation / DORA time-to-restore): from the RUN's completion
    # (i.e. when the failure actually surfaced) to the fix PR being raised.
    mttr_epoch = func.extract("epoch", Remediation.pr_raised_at - WorkflowRun.completed_at)
    mttr_seconds = (
        await db.execute(
            select(func.avg(mttr_epoch))
            .select_from(Remediation)
            .join(WorkflowRun, Remediation.workflow_run_id == WorkflowRun.id)
            .where(Remediation.pr_raised_at.is_not(None), WorkflowRun.completed_at.is_not(None), *rem_app)
        )
    ).scalar_one()
    mttr_seconds = round(float(mttr_seconds)) if mttr_seconds is not None else None

    # MTTD (Mean Time To Detection): run completion -> remediation analysis kicked off.
    mttd_epoch = func.extract("epoch", Remediation.created_at - WorkflowRun.completed_at)
    mttd_seconds = (
        await db.execute(
            select(func.avg(mttd_epoch))
            .select_from(Remediation)
            .join(WorkflowRun, Remediation.workflow_run_id == WorkflowRun.id)
            .where(WorkflowRun.completed_at.is_not(None), *rem_app)
        )
    ).scalar_one()
    mttd_seconds = round(float(mttd_seconds)) if mttd_seconds is not None else None

    # Open vulnerabilities by (in-context) severity.
    sev = func.coalesce(VulnerabilityFinding.severity_in_context, VulnerabilityFinding.severity)
    vuln_rows = await db.execute(
        select(sev.label("sev"), func.count().label("count"))
        .where(VulnerabilityFinding.status == "open", *vuln_app)
        .group_by(sev)
    )
    open_vulns_by_severity: dict[str, int] = {}
    open_vulns_total = 0
    for row in vuln_rows.all():
        key = (row.sev or "unknown").lower()
        open_vulns_by_severity[key] = open_vulns_by_severity.get(key, 0) + row.count
        open_vulns_total += row.count

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "success_count": success_runs,
        "failure_count": failed_runs,
        "other_count": other_runs,
        "failure_rate": failure_rate,
        "success_rate": success_rate,
        "runs_per_day": runs_per_day,
        "remediations_raised": remediations_raised,
        "avg_analysis_seconds": avg_analysis_seconds,
        "avg_time_to_pr_seconds": avg_time_to_pr_seconds,
        "mttr_seconds": mttr_seconds,
        "mttd_seconds": mttd_seconds,
        "open_vulns_total": open_vulns_total,
        "open_vulns_by_severity": open_vulns_by_severity,
        "top_failing_repos": top_failing_repos,
        "top_failing_workflows": top_failing_workflows,
        "run_trend": run_trend,
    }
