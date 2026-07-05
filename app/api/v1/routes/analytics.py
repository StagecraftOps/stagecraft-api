from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.remediation import Remediation
from app.models.user import User
from app.models.workflow_run import WorkflowRun

router = APIRouter()

@router.get("/")
async def get_analytics(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregate pipeline statistics.

    Response shape matches the frontend ``AnalyticsData`` contract: ``success_rate``
    and ``failure_rate`` are fractions in [0, 1], ``top_failing_repos`` is a list of
    ``{repo, count}``, and ``run_trend`` is a daily series over the last 30 days.
    """
    total_runs = (
        await db.execute(select(func.count()).select_from(WorkflowRun))
    ).scalar_one() or 0

    failed_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion == "failure")
        )
    ).scalar_one() or 0

    success_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion == "success")
        )
    ).scalar_one() or 0

    failure_rate = round(failed_runs / total_runs, 4) if total_runs else 0.0
    success_rate = round(success_runs / total_runs, 4) if total_runs else 0.0

    top_failing_result = await db.execute(
        select(WorkflowRun.repo_name, func.count().label("count"))
        .where(WorkflowRun.conclusion == "failure")
        .group_by(WorkflowRun.repo_name)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_failing_repos = [
        {"repo": row.repo_name, "count": row.count} for row in top_failing_result.all()
    ]

    since = datetime.now(timezone.utc) - timedelta(days=30)
    day = func.date(WorkflowRun.created_at)
    trend_result = await db.execute(
        select(
            day.label("date"),
            func.sum(case((WorkflowRun.conclusion == "success", 1), else_=0)).label("success"),
            func.sum(case((WorkflowRun.conclusion == "failure", 1), else_=0)).label("failed"),
        )
        .where(WorkflowRun.created_at >= since)
        .group_by(day)
        .order_by(day)
    )
    run_trend = [
        {"date": str(row.date), "success": int(row.success or 0), "failed": int(row.failed or 0)}
        for row in trend_result.all()
    ]

    # A fix is "raised" once a PR has been opened for it. The Remediation
    # status enum is pending|analyzing|analyzed|pr_raised|helpful|failed —
    # there is no "completed", so the old check always returned 0.
    remediations_raised = (
        await db.execute(
            select(func.count())
            .select_from(Remediation)
            .where(Remediation.status.in_(["pr_raised", "helpful"]))
        )
    ).scalar_one() or 0

    # Real "time to fix suggestion": how long from a remediation being created
    # (failure detected) to analysis completing. updated_at is bumped when the
    # agent finishes and sets status=analyzed, so this is a genuine, populated
    # latency — no more hardcoded "~5m".
    epoch = func.extract("epoch", Remediation.updated_at - Remediation.created_at)
    avg_analysis_seconds = (
        await db.execute(
            select(func.avg(epoch)).where(
                Remediation.status.in_(["analyzed", "pr_raised", "helpful"])
            )
        )
    ).scalar_one()
    avg_analysis_seconds = round(float(avg_analysis_seconds)) if avg_analysis_seconds is not None else None

    # True time-to-PR, only for remediations whose PR was actually raised.
    # Null (shown as "—") until at least one PR is opened, which is honest.
    epoch_pr = func.extract("epoch", Remediation.pr_raised_at - Remediation.created_at)
    avg_time_to_pr_seconds = (
        await db.execute(
            select(func.avg(epoch_pr)).where(Remediation.pr_raised_at.is_not(None))
        )
    ).scalar_one()
    avg_time_to_pr_seconds = round(float(avg_time_to_pr_seconds)) if avg_time_to_pr_seconds is not None else None

    # Honest run breakdown: success + failure + other = completed runs. The
    # frontend can render a real three-way split instead of two rates that
    # look broken because they don't add to 100.
    completed_runs = (
        await db.execute(
            select(func.count()).select_from(WorkflowRun).where(WorkflowRun.conclusion.is_not(None))
        )
    ).scalar_one() or 0
    other_runs = max(completed_runs - success_runs - failed_runs, 0)

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "success_count": success_runs,
        "failure_count": failed_runs,
        "other_count": other_runs,
        "failure_rate": failure_rate,
        "success_rate": success_rate,
        "remediations_raised": remediations_raised,
        "avg_analysis_seconds": avg_analysis_seconds,
        "avg_time_to_pr_seconds": avg_time_to_pr_seconds,
        "top_failing_repos": top_failing_repos,
        "run_trend": run_trend,
    }
