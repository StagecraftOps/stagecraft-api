import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationList, OrganizationResponse
from app.core.config import settings
from app.services.github import GitHubService
from app.services.github_app import get_installation_token_for_org
from app.services.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)

router = APIRouter()

_publisher = SQSPublisher()

async def _get_owned_org(org_login: str, user: User, db: AsyncSession) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.login == org_login, Organization.owner_id == user.id
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org

@router.get("/", response_model=OrganizationList)
async def list_orgs(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationList:
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    return OrganizationList(
        organizations=[OrganizationResponse.model_validate(o) for o in orgs],
        total=len(orgs),
    )

@router.get("/install")
async def install_app(
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if not settings.GITHUB_APP_SLUG:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_APP_SLUG is not configured",
        )
    return RedirectResponse(
        url=f"https://github.com/apps/{settings.GITHUB_APP_SLUG}/installations/new"
    )

@router.get("/{org_login}/repos")
async def list_org_repos(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List every repo the installation can see, plus which ones are
    currently marked active for analysis (the 'Select Scope' wizard step)."""
    org = await _get_owned_org(org_login, user, db)

    token = await get_installation_token_for_org(org_login)
    github = GitHubService(token)
    repos = await github.get_org_repos(org_login)

    scope_rows = await db.execute(
        text("SELECT repo_name, is_active FROM org_repo_scope WHERE org_id = :org_id"),
        {"org_id": str(org.id)},
    )
    scope = scope_rows.fetchall()
    has_scope = len(scope) > 0
    active_names = {r[0] for r in scope if r[1]}

    return {
        "repos": [
            {
                "name": r["name"],
                "private": r.get("private", False),
                "language": r.get("language"),
                "is_active": (r["name"] in active_names) if has_scope else True,
            }
            for r in repos
        ],
        "total": len(repos),
    }

class ScopeUpdateRequest(BaseModel):
    active_repo_names: list[str]

@router.put("/{org_login}/repos/scope")
async def set_org_repo_scope(
    org_login: str,
    body: ScopeUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Persist the user's repo selection, then kick off (background) estate
    discovery scoped to only those repos."""
    org = await _get_owned_org(org_login, user, db)

    await db.execute(
        text("DELETE FROM org_repo_scope WHERE org_id = :org_id"),
        {"org_id": str(org.id)},
    )
    for repo_name in body.active_repo_names:
        await db.execute(
            text(
                """
                INSERT INTO org_repo_scope (id, org_id, repo_name, is_active, created_at)
                VALUES (:id, :org_id, :repo_name, true, now())
                """
            ),
            {"id": str(uuid.uuid4()), "org_id": str(org.id), "repo_name": repo_name},
        )
    await db.commit()

    await _publisher.publish({"event_type": "backfill_org", "org_login": org_login})

    return {"status": "scope_saved", "active_count": len(body.active_repo_names)}

@router.get("/{org_login}/sync-progress")
async def get_sync_progress(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await _get_owned_org(org_login, user, db)

    rows = await db.execute(
        text(
            """
            SELECT repo_name, status, runs_synced, error, updated_at
            FROM org_sync_progress WHERE org_id = :org_id
            ORDER BY repo_name
            """
        ),
        {"org_id": str(org.id)},
    )
    repo_progress = [
        {
            "repo_name": r[0],
            "status": r[1],
            "runs_synced": r[2],
            "error": r[3],
            "updated_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows.fetchall()
    ]
    return {
        "org_login": org_login,
        "org_sync_status": org.sync_status,
        "repos": repo_progress,
        "total": len(repo_progress),
        "completed": sum(1 for r in repo_progress if r["status"] in ("completed", "failed")),
    }

@router.delete("/{org_login}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_org(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    org = await _get_owned_org(org_login, user, db)
    await db.delete(org)
    await db.commit()
