from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.context_parser import parse_context_file
from app.db.base import get_db
from app.models.application_context import ApplicationContext
from app.models.user import User
from app.schemas.application_context import (
    ApplicationContextCreate,
    ApplicationContextList,
    ApplicationContextResponse,
)

router = APIRouter()

_ASSIGNABLE = [
    "app_name",
    "language",
    "framework",
    "regulatory_scope",
    "data_classification",
    "risk_tier",
    "team_owner",
    "security_contact",
    "notes",
]

async def _upsert(db: AsyncSession, org_login: str, repo_name: str, fields: dict, source: str, raw: str | None) -> ApplicationContext:
    existing = (
        await db.execute(
            select(ApplicationContext).where(
                ApplicationContext.org_login == org_login,
                ApplicationContext.repo_name == repo_name,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = ApplicationContext(org_login=org_login, repo_name=repo_name)
        db.add(existing)

    for key in _ASSIGNABLE:
        if key in fields and fields[key] is not None:
            setattr(existing, key, fields[key])
    existing.source = source
    if raw is not None:
        existing.raw_content = raw

    await db.commit()
    await db.refresh(existing)
    return existing

@router.post("/", response_model=ApplicationContextResponse, status_code=status.HTTP_201_CREATED)
async def create_application_context(
    payload: ApplicationContextCreate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationContextResponse:
    ctx = await _upsert(
        db,
        payload.org_login,
        payload.repo_name,
        payload.model_dump(),
        payload.source,
        payload.raw_content,
    )
    return ApplicationContextResponse.model_validate(ctx)

@router.post("/upload", response_model=ApplicationContextResponse, status_code=status.HTTP_201_CREATED)
async def upload_application_context(
    org_login: str = Form(..., max_length=255),
    repo_name: str = Form(..., max_length=255),
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationContextResponse:
    content = (await file.read()).decode("utf-8", errors="replace")
    fields = parse_context_file(content)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No recognized application-context fields found in the uploaded file.",
        )
    ctx = await _upsert(db, org_login, repo_name, fields, "upload", content)
    return ApplicationContextResponse.model_validate(ctx)

@router.get("/", response_model=ApplicationContextList)
async def list_application_contexts(
    org_login: str | None = Query(default=None, max_length=255),
    repo_name: str | None = Query(default=None, max_length=255),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationContextList:
    query = select(ApplicationContext)
    count_query = select(func.count()).select_from(ApplicationContext)
    if org_login:
        query = query.where(ApplicationContext.org_login == org_login)
        count_query = count_query.where(ApplicationContext.org_login == org_login)
    if repo_name:
        query = query.where(ApplicationContext.repo_name == repo_name)
        count_query = count_query.where(ApplicationContext.repo_name == repo_name)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(ApplicationContext.updated_at.desc())
    contexts = (await db.execute(query)).scalars().all()
    return ApplicationContextList(
        contexts=[ApplicationContextResponse.model_validate(c) for c in contexts], total=total
    )

@router.get("/{org_login}/{repo_name}", response_model=ApplicationContextResponse)
async def get_application_context(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationContextResponse:
    ctx = (
        await db.execute(
            select(ApplicationContext).where(
                ApplicationContext.org_login == org_login,
                ApplicationContext.repo_name == repo_name,
            )
        )
    ).scalar_one_or_none()
    if not ctx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application context not found")
    return ApplicationContextResponse.model_validate(ctx)
