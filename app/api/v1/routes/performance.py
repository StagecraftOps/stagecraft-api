from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.job_run import JobRun
from app.models.user import User
from app.models.workflow_run import WorkflowRun
from app.schemas.job_run import LongestJobEntry, LongestWorkflowEntry, RunnerBreakdownEntry

router = APIRouter()

# A 'cancelled' job/run's duration is (completed_at - started_at) same as any
# other, but for a run stuck queued waiting on a runner, that number measures
# queue time, not compute time -- verified live, a matrix-heavy workflow in
# this org queued for 24-55h before GitHub's own queued-job timeout cancelled
# it, dwarfing every genuine (a few minutes) duration and making the whole
# "longest running" ranking pure noise. Excluded from both queries below;
# 'failure' is kept, since a test that ran for 10 real minutes before failing
# is still a genuine duration worth ranking.
_EXCLUDED_CONCLUSIONS = ("cancelled",)


@router.get("/{org_login}/performance/longest-jobs", response_model=list[LongestJobEntry])
async def longest_jobs(
    org_login: str,
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LongestJobEntry]:
    """Longest-running jobs across an org's recent runs — pure duration ranking, no AI."""
    result = await db.execute(
        select(JobRun, WorkflowRun.repo_name)
        .join(WorkflowRun, WorkflowRun.id == JobRun.workflow_run_id)
        .where(
            WorkflowRun.org_login == org_login,
            JobRun.duration_seconds.is_not(None),
            JobRun.conclusion.not_in(_EXCLUDED_CONCLUSIONS),
        )
        .order_by(JobRun.duration_seconds.desc())
        .limit(limit)
    )
    return [
        LongestJobEntry(
            job_name=job.job_name,
            repo_name=repo_name,
            workflow_run_id=job.workflow_run_id,
            duration_seconds=job.duration_seconds,
        )
        for job, repo_name in result.all()
    ]


@router.get("/{org_login}/performance/longest-workflows", response_model=list[LongestWorkflowEntry])
async def longest_workflows(
    org_login: str,
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LongestWorkflowEntry]:
    """Longest-running workflow runs (completed_at - started_at) across an org."""
    result = await db.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.org_login == org_login,
            WorkflowRun.started_at.is_not(None),
            WorkflowRun.completed_at.is_not(None),
            WorkflowRun.conclusion.not_in(_EXCLUDED_CONCLUSIONS),
        )
    )
    runs = result.scalars().all()
    ranked = sorted(
        runs, key=lambda r: (r.completed_at - r.started_at).total_seconds(), reverse=True
    )[:limit]
    return [
        LongestWorkflowEntry(
            workflow_name=r.workflow_name,
            repo_name=r.repo_name,
            workflow_run_id=r.id,
            duration_seconds=int((r.completed_at - r.started_at).total_seconds()),
        )
        for r in ranked
    ]


@router.get("/{org_login}/performance/runner-breakdown", response_model=list[RunnerBreakdownEntry])
async def runner_breakdown(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RunnerBreakdownEntry]:
    """Job count + avg duration grouped by runner label combo (e.g.
    ["ubuntu-latest"] or ["self-hosted","linux","x64"]) -- synced from
    GitHub's Jobs API `labels` field (job_timing.py), not the ephemeral
    `runner_name` (ephemeral per-job instance id, uninformative for a type
    breakdown).

    Deliberately NOT filtered by conclusion, unlike the two endpoints above:
    a job that never got a runner assigned (runner_labels IS NULL) forms its
    own "no runner assigned" bucket here, which is real signal about queue/
    capacity pressure, not noise to exclude -- the two ranking endpoints
    above exclude cancelled runs because a stuck run's *duration* is
    meaningless, but a stuck run's *existence* is exactly what this endpoint
    should surface.
    """
    result = await db.execute(
        select(
            JobRun.runner_labels,
            func.count().label("job_count"),
            func.avg(JobRun.duration_seconds).label("avg_duration"),
        )
        .join(WorkflowRun, WorkflowRun.id == JobRun.workflow_run_id)
        .where(WorkflowRun.org_login == org_login)
        .group_by(JobRun.runner_labels)
        .order_by(func.count().desc())
    )
    return [
        RunnerBreakdownEntry(
            runner_labels=row.runner_labels,
            job_count=row.job_count,
            avg_duration_seconds=round(row.avg_duration, 1) if row.avg_duration is not None else None,
        )
        for row in result.all()
    ]
