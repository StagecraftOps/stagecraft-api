from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_access_token
from app.db.base import get_db
from app.models.user import User

AUTH_COOKIE_NAME = "stagecraft_token"

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

async def verify_internal_request(
    x_internal_api_key: str | None = Header(default=None),
) -> None:
    if not settings.INTERNAL_API_KEY or x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
