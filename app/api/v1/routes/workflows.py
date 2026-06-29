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

async def _get_org_with_token(db: AsyncSession, org_login: str) -> tuple[Organization, str]:
    """Return the org and the org owner's encrypted GitHub token.

    Any authenticated user can view any connected org's workflows — we use
    the org owner's stored token for the GitHub API call so the caller's
    own GitHub account doesn't need access to the org.
    """
    result = await db.execute(
        select(Organization, User).join(User, User.id == Organization.owner_id)
        .where(Organization.login == org_login)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org, owner = row
    return org, owner.access_token_encrypted

@router.get("/{org_login}/workflows", response_model=WorkflowList)
async def list_all_workflows(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowList:
    """Fetch all repos for an org and return a flat list of all workflows."""
    _org, enc_token = await _get_org_with_token(db, org_login)

    github = GitHubService(decrypt_token(enc_token))
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
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowList:
    """Fetch workflows for a single repository."""
    _org, enc_token = await _get_org_with_token(db, org_login)

    github = GitHubService(decrypt_token(enc_token))
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
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch recent runs for a specific workflow."""
    _org, enc_token = await _get_org_with_token(db, org_login)

    github = GitHubService(decrypt_token(enc_token))
    try:
        runs = await github.get_workflow_runs(org_login, repo, workflow_id, per_page=per_page)
        return {"runs": runs, "total": len(runs)}
    finally:
        await github.aclose()
