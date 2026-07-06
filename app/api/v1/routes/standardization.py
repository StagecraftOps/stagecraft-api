import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.standardization import PatternCluster, TemplateDiff, WorkflowTemplate
from app.models.user import User
from app.schemas.standardization import (
    PatternClusterList,
    PatternClusterResponse,
    StandardizationAnalyzeRequest,
    TemplateDiffList,
    TemplateDiffResponse,
    WorkflowTemplateCreate,
    WorkflowTemplateList,
    WorkflowTemplateResponse,
)
from app.services.sqs_publisher import SQSPublisher

router = APIRouter()

_publisher = SQSPublisher()

@router.post("/{org_login}/templates", response_model=WorkflowTemplateResponse)
async def create_template(
    org_login: str,
    body: WorkflowTemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateResponse:
    template = WorkflowTemplate(
        org_login=org_login,
        name=body.name,
        description=body.description,
        template_yaml=body.template_yaml,
        created_by=user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return WorkflowTemplateResponse.model_validate(template)

@router.get("/{org_login}/templates", response_model=WorkflowTemplateList)
async def list_templates(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTemplateList:
    result = await db.execute(
        select(WorkflowTemplate)
        .where(WorkflowTemplate.org_login == org_login, WorkflowTemplate.is_active.is_(True))
        .order_by(WorkflowTemplate.created_at.desc())
    )
    templates = result.scalars().all()
    return WorkflowTemplateList(templates=[WorkflowTemplateResponse.model_validate(t) for t in templates])

@router.delete("/{org_login}/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_template(
    org_login: str,
    template_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.id == template_id, WorkflowTemplate.org_login == org_login
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    template.is_active = False
    await db.commit()

@router.post("/{org_login}/repos/{repo_name}/standardization/analyze")
async def analyze_standardization(
    org_login: str,
    repo_name: str,
    body: StandardizationAnalyzeRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _publisher.publish({
        "event_type": "run_template_diff",
        "org_login": org_login,
        "repo_name": repo_name,
        "ref": body.ref,
    })
    await _publisher.publish({
        "event_type": "run_pattern_frequency",
        "org_login": org_login,
        "repo_name": repo_name,
        "ref": body.ref,
    })
    return {"status": "enqueued", "org_login": org_login, "repo_name": repo_name}

@router.get("/{org_login}/repos/{repo_name}/standardization/diffs", response_model=TemplateDiffList)
async def get_template_diffs(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateDiffList:
    result = await db.execute(
        select(TemplateDiff)
        .where(TemplateDiff.org_login == org_login, TemplateDiff.repo_name == repo_name)
        .order_by(TemplateDiff.computed_at.desc())
    )
    diffs = result.scalars().all()
    return TemplateDiffList(diffs=[TemplateDiffResponse.model_validate(d) for d in diffs])

@router.get("/{org_login}/standardization/patterns", response_model=PatternClusterList)
async def get_pattern_clusters(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatternClusterList:
    result = await db.execute(
        select(PatternCluster)
        .where(PatternCluster.org_login == org_login)
        .order_by(PatternCluster.occurrence_count.desc())
    )
    patterns = result.scalars().all()
    return PatternClusterList(patterns=[PatternClusterResponse.model_validate(p) for p in patterns])
