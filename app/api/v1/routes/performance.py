from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.job_run import JobRun
from app.models.user import User
from app.models.workflow_run import WorkflowRun
from app.schemas.job_run import LongestJobEntry, LongestWorkflowEntry

router = APIRouter()


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
        .where(WorkflowRun.org_login == org_login, JobRun.duration_seconds.is_not(None))
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
