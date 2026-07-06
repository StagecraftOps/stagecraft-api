import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationList, OrganizationResponse
from app.core.config import settings
from app.services.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)

router = APIRouter()

_publisher = SQSPublisher()

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

@router.delete("/{org_login}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_org(
    org_login: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Organization).where(
            Organization.login == org_login, Organization.owner_id == user.id
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    await db.delete(org)
    await db.commit()
