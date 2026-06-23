"""Shared FastAPI dependencies for the v1 API.

Centralizes JWT-cookie authentication so every route resolves the current user
the same way (previously each route re-implemented this and read a cookie whose
name did not match the frontend contract).
"""
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_access_token
from app.db.base import get_db
from app.models.user import User

AUTH_COOKIE_NAME = "agora_token"

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> User:
    """Resolve the authenticated user from the JWT cookie, or raise 401/404."""
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
    """Gate /internal/* routes to callers holding the shared service secret.

    Not a substitute for network isolation — these routes are also ClusterIP
    -only — but it stops any other in-cluster pod from calling them, and an
    unset INTERNAL_API_KEY (e.g. a misconfigured deploy) fails closed rather
    than silently accepting every request.
    """
    if not settings.INTERNAL_API_KEY or x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
