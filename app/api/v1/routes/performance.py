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

_EXCLUDED_CONCLUSIONS = ("cancelled",)

@router.get("/{org_login}/performance/longest-jobs", response_model=list[LongestJobEntry])
async def longest_jobs(
    org_login: str,
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LongestJobEntry]:
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
