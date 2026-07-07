import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_token
from app.db.base import get_db
from app.models.job_run import CriticalPathResult, JobRun
from app.models.organization import Organization
from app.models.user import User
from app.models.workflow_run import WorkflowRun
from app.schemas.job_run import CriticalPathResponse, JobRunList, JobRunResponse
from app.schemas.workflow import WorkflowRunList, WorkflowRunResponse
from app.services.github import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter()

async def _visible_org_logins(db: AsyncSession) -> list[str]:
    result = await db.execute(select(Organization.login))
    return list(result.scalars().all())

@router.get("/", response_model=WorkflowRunList)
async def list_recent_runs(
    org_login: str | None = Query(default=None, max_length=255),
    repo_name: str | None = Query(default=None, max_length=255),
    application_id: uuid.UUID | None = Query(default=None),
    run_status: str | None = Query(default=None, alias="status", max_length=64),
    conclusion: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowRunList:
    visible_logins = await _visible_org_logins(db)
    if not visible_logins:
        return WorkflowRunList(runs=[], total=0)

    if org_login and org_login not in visible_logins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    query = select(WorkflowRun).where(WorkflowRun.org_login.in_(visible_logins))
    count_query = select(func.count()).select_from(WorkflowRun).where(
        WorkflowRun.org_login.in_(visible_logins)
    )

    if org_login:
        query = query.where(WorkflowRun.org_login == org_login)
        count_query = count_query.where(WorkflowRun.org_login == org_login)
    if repo_name:
        query = query.where(WorkflowRun.repo_name == repo_name)
        count_query = count_query.where(WorkflowRun.repo_name == repo_name)
    if application_id:
        query = query.where(WorkflowRun.application_id == application_id)
        count_query = count_query.where(WorkflowRun.application_id == application_id)
    if run_status:
        query = query.where(WorkflowRun.status == run_status)
        count_query = count_query.where(WorkflowRun.status == run_status)
    if conclusion:
        query = query.where(WorkflowRun.conclusion == conclusion)
        count_query = count_query.where(WorkflowRun.conclusion == conclusion)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(WorkflowRun.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return WorkflowRunList(
        runs=[WorkflowRunResponse.model_validate(r) for r in runs],
        total=total,
    )

async def _get_org_owner_token(db: AsyncSession, org_login: str) -> str:
    result = await db.execute(
        select(User).join(Organization, Organization.owner_id == User.id)
        .where(Organization.login == org_login)
    )
    owner = result.scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return owner.access_token_encrypted

@router.get("/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    db_run = result.scalar_one_or_none()
    if not db_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return WorkflowRunResponse.model_validate(db_run).model_dump()

@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.core.scrubber import scrub

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    db_run = result.scalar_one_or_none()
    if not db_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    enc_token = await _get_org_owner_token(db, db_run.org_login)
    github = GitHubService(decrypt_token(enc_token))
    try:
        raw_logs = await github.get_run_logs_text(
            db_run.org_login, db_run.repo_name, db_run.github_run_id
        )
        return {"logs": scrub(raw_logs)}
    except Exception as exc:
        logger.warning("Failed to fetch logs for run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch logs from GitHub. Logs may have expired (GitHub keeps them ~90 days).",
        )
    finally:
        await github.aclose()

@router.get("/{run_id}/jobs", response_model=JobRunList)
async def get_run_jobs(
    run_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRunList:
    result = await db.execute(
        select(JobRun).where(JobRun.workflow_run_id == run_id).order_by(JobRun.started_at)
    )
    jobs = result.scalars().all()
    return JobRunList(jobs=[JobRunResponse.model_validate(j) for j in jobs])

@router.get("/{run_id}/critical-path", response_model=CriticalPathResponse)
async def get_run_critical_path(
    run_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CriticalPathResponse:
    result = await db.execute(
        select(CriticalPathResult).where(CriticalPathResult.workflow_run_id == run_id)
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Critical path not yet computed for this run")
    return CriticalPathResponse.model_validate(cp)
