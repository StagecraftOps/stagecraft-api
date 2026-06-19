import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_token
from app.db.base import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationList, OrganizationResponse
from app.services.github import GitHubService
from app.services.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)

router = APIRouter()

WEBHOOK_URL = "http://webhook-service:8001/webhooks/github"

_publisher = SQSPublisher()

@router.get("/", response_model=OrganizationList)
async def list_orgs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationList:
    """List all organizations connected by the current user."""
    result = await db.execute(
        select(Organization).where(Organization.owner_id == user.id)
    )
    orgs = result.scalars().all()
    return OrganizationList(
        organizations=[OrganizationResponse.model_validate(o) for o in orgs],
        total=len(orgs),
    )

@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def connect_org(
    body: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Connect a GitHub organization by installing a webhook."""
    github = GitHubService(decrypt_token(user.access_token_encrypted))
    try:
        try:
            gh_org = await github._get(f"/orgs/{body.login}")
        except Exception as exc:
            logger.warning("Failed to fetch org %s from GitHub: %s", body.login, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not fetch organization from GitHub.",
            )

        existing = await db.execute(
            select(Organization).where(Organization.login == body.login)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization already connected",
            )

        webhook_secret = secrets.token_hex(32)
        try:
            webhook_data = await github.create_webhook(body.login, webhook_secret, WEBHOOK_URL)
            webhook_id = webhook_data.get("id")
        except Exception as exc:
            logger.warning("Failed to create webhook for org %s: %s", body.login, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create webhook.",
            )
    finally:
        await github.aclose()

    org = Organization(
        github_org_id=gh_org["id"],
        login=gh_org["login"],
        name=gh_org.get("name"),
        avatar_url=gh_org.get("avatar_url"),
        webhook_secret=webhook_secret,
        webhook_id=webhook_id,
        owner_id=user.id,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    try:
        await _publisher.publish({"event_type": "backfill_org", "org_login": org.login})
    except Exception as exc:
        logger.warning("Failed to enqueue backfill for org %s: %s", org.login, exc)

    return OrganizationResponse.model_validate(org)

@router.delete("/{org_login}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_org(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect an organization: remove webhook and delete from DB."""
    result = await db.execute(
        select(Organization).where(
            Organization.login == org_login, Organization.owner_id == user.id
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    github = GitHubService(decrypt_token(user.access_token_encrypted))
    try:
        if org.webhook_id:
            await github.delete_webhook(org_login, org.webhook_id)
    except Exception as exc:
        logger.warning(
            "Failed to delete webhook %s for org %s (continuing with DB removal): %s",
            org.webhook_id,
            org_login,
            exc,
        )
    finally:
        await github.aclose()

    await db.delete(org)
    await db.commit()
