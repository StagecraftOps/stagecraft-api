import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_token
from app.db.base import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.workflow import WorkflowList, WorkflowSummary
from app.services.github import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter()

async def _get_org(db: AsyncSession, org_login: str, user_id: object) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.login == org_login, Organization.owner_id == user_id
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org

@router.get("/{org_login}/workflows", response_model=WorkflowList)
async def list_all_workflows(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowList:
    """Fetch all repos for an org and return a flat list of all workflows."""
    await _get_org(db, org_login, user.id)

    github = GitHubService(decrypt_token(user.access_token_encrypted))
    try:
        repos = await github.get_org_repos(org_login)

        async def _get_repo_workflows(repo: dict) -> list[WorkflowSummary]:
            try:
                raw_workflows = await github.get_repo_workflows(org_login, repo["name"])
                return [
                    WorkflowSummary(
                        id=wf["id"],
                        name=wf["name"],
                        path=wf["path"],
                        state=wf["state"],
                        html_url=wf["html_url"],
                        repo_name=repo["name"],
                        org_login=org_login,
                    )
                    for wf in raw_workflows
                ]
            except Exception as exc:
                logger.warning(
                    "Failed to list workflows for %s/%s: %s", org_login, repo["name"], exc
                )
                return []

        results = await asyncio.gather(*[_get_repo_workflows(repo) for repo in repos])
        all_workflows: list[WorkflowSummary] = []
        for batch in results:
            all_workflows.extend(batch)

        return WorkflowList(workflows=all_workflows, total=len(all_workflows))
    finally:
        await github.aclose()

@router.get("/{org_login}/{repo}/workflows", response_model=WorkflowList)
async def list_repo_workflows(
    org_login: str,
    repo: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowList:
    """Fetch workflows for a single repository."""
    await _get_org(db, org_login, user.id)

    github = GitHubService(decrypt_token(user.access_token_encrypted))
    try:
        raw_workflows = await github.get_repo_workflows(org_login, repo)
        workflows = [
            WorkflowSummary(
                id=wf["id"],
                name=wf["name"],
                path=wf["path"],
                state=wf["state"],
                html_url=wf["html_url"],
                repo_name=repo,
                org_login=org_login,
            )
            for wf in raw_workflows
        ]
        return WorkflowList(workflows=workflows, total=len(workflows))
    finally:
        await github.aclose()

@router.get("/{org_login}/{repo}/workflows/{workflow_id}/runs")
async def list_workflow_runs(
    org_login: str,
    repo: str,
    workflow_id: int,
    per_page: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch recent runs for a specific workflow."""
    await _get_org(db, org_login, user.id)

    github = GitHubService(decrypt_token(user.access_token_encrypted))
    try:
        runs = await github.get_workflow_runs(org_login, repo, workflow_id, per_page=per_page)
        return {"runs": runs, "total": len(runs)}
    finally:
        await github.aclose()
