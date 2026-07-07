import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.routes.orgs import _get_owned_org
from app.db.base import get_db
from app.models.application import Application, ApplicationRepo
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Domain tables whose application_id we keep in sync with repo membership.
_SYNCED_TABLES = [
    "workflow_runs",
    "remediations",
    "vulnerability_findings",
    "pr_reviews",
    "agent_runs",
    "application_contexts",
]

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "app"

class ApplicationCreate(BaseModel):
    name: str
    description: str | None = None
    repo_names: list[str] = []

class ApplicationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class RepoScopeUpdate(BaseModel):
    repo_names: list[str]

async def _app_repos(db: AsyncSession, application_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(ApplicationRepo.repo_name).where(ApplicationRepo.application_id == application_id)
    )
    return [r[0] for r in rows.all()]

def _serialize(app: Application, repos: list[str]) -> dict:
    return {
        "id": str(app.id),
        "org_login": app.org_login,
        "name": app.name,
        "slug": app.slug,
        "description": app.description,
        "repo_names": repos,
        "repo_count": len(repos),
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }

async def _owned_application(
    org_login: str, application_id: uuid.UUID, user: User, db: AsyncSession
) -> Application:
    await _get_owned_org(org_login, user, db)
    result = await db.execute(
        select(Application).where(
            Application.id == application_id, Application.org_login == org_login
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app

async def _sync_membership(
    db: AsyncSession, org_login: str, application_id: uuid.UUID, repo_names: list[str]
) -> None:
    """Replace the app's repo set, and keep application_id on domain rows in sync:
    clear this app's id from rows no longer in the set, then stamp it on rows in the set."""
    # Clear application_id from all domain rows currently tagged with this app.
    for table in _SYNCED_TABLES:
        await db.execute(
            text(f"UPDATE {table} SET application_id = NULL WHERE application_id = :app"),
            {"app": str(application_id)},
        )

    # Rebuild the membership rows.
    await db.execute(
        text("DELETE FROM application_repos WHERE application_id = :app"),
        {"app": str(application_id)},
    )
    org_row = (
        await db.execute(
            text("SELECT id FROM organizations WHERE login = :login"), {"login": org_login}
        )
    ).first()
    org_id = str(org_row[0]) if org_row else None

    for repo in repo_names:
        await db.execute(
            text(
                """
                INSERT INTO application_repos (id, application_id, org_id, org_login, repo_name, created_at)
                VALUES (:id, :app, :org_id, :org_login, :repo, now())
                ON CONFLICT (org_id, repo_name) DO UPDATE SET application_id = EXCLUDED.application_id
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "app": str(application_id),
                "org_id": org_id,
                "org_login": org_login,
                "repo": repo,
            },
        )
        # Stamp application_id onto existing + historical domain rows for this repo.
        for table in _SYNCED_TABLES:
            await db.execute(
                text(
                    f"UPDATE {table} SET application_id = :app "
                    "WHERE org_login = :org AND repo_name = :repo"
                ),
                {"app": str(application_id), "org": org_login, "repo": repo},
            )

@router.get("/{org_login}/applications")
async def list_applications(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_owned_org(org_login, user, db)
    result = await db.execute(
        select(Application).where(Application.org_login == org_login).order_by(Application.created_at)
    )
    apps = result.scalars().all()
    out = []
    for app in apps:
        out.append(_serialize(app, await _app_repos(db, app.id)))
    return {"applications": out, "total": len(out)}

@router.post("/{org_login}/applications", status_code=status.HTTP_201_CREATED)
async def create_application(
    org_login: str,
    body: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await _get_owned_org(org_login, user, db)
    slug = _slugify(body.name)

    exists = await db.execute(
        select(Application).where(Application.org_id == org.id, Application.slug == slug)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An application with a similar name already exists")

    app = Application(
        org_id=org.id,
        org_login=org_login,
        name=body.name,
        slug=slug,
        description=body.description,
    )
    db.add(app)
    await db.flush()

    if body.repo_names:
        await _sync_membership(db, org_login, app.id, body.repo_names)

    await db.commit()
    await db.refresh(app)
    return _serialize(app, await _app_repos(db, app.id))

@router.get("/{org_login}/applications/{application_id}")
async def get_application(
    org_login: str,
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    app = await _owned_application(org_login, application_id, user, db)
    return _serialize(app, await _app_repos(db, app.id))

@router.put("/{org_login}/applications/{application_id}")
async def update_application(
    org_login: str,
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    app = await _owned_application(org_login, application_id, user, db)
    if body.name is not None:
        app.name = body.name
        app.slug = _slugify(body.name)
    if body.description is not None:
        app.description = body.description
    await db.commit()
    await db.refresh(app)
    return _serialize(app, await _app_repos(db, app.id))

@router.put("/{org_login}/applications/{application_id}/repos")
async def set_application_repos(
    org_login: str,
    application_id: uuid.UUID,
    body: RepoScopeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    app = await _owned_application(org_login, application_id, user, db)
    await _sync_membership(db, org_login, app.id, body.repo_names)
    await db.commit()
    return _serialize(app, await _app_repos(db, app.id))

@router.delete("/{org_login}/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    org_login: str,
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    app = await _owned_application(org_login, application_id, user, db)
    # Clear application_id from domain rows before removing the app.
    for table in _SYNCED_TABLES:
        await db.execute(
            text(f"UPDATE {table} SET application_id = NULL WHERE application_id = :app"),
            {"app": str(app.id)},
        )
    await db.delete(app)
    await db.commit()
