import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.vulnerability_finding import VulnerabilityFinding
from app.schemas.vulnerability_finding import VulnerabilityFindingList, VulnerabilityFindingResponse
from app.services.sqs_publisher import SQSPublisher

router = APIRouter()
_publisher = SQSPublisher()

class RemediationTriggerRequest(BaseModel):
    org_login: str
    repo_name: str
    finding_id: str | None = None

@router.get("/", response_model=VulnerabilityFindingList)
async def list_vulnerability_findings(
    org_login: str | None = Query(default=None, max_length=255),
    repo_name: str | None = Query(default=None, max_length=255),
    application_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityFindingList:
    query = select(VulnerabilityFinding)
    count_query = select(func.count()).select_from(VulnerabilityFinding)

    for column, value in (
        (VulnerabilityFinding.org_login, org_login),
        (VulnerabilityFinding.repo_name, repo_name),
        (VulnerabilityFinding.application_id, application_id),
        (VulnerabilityFinding.status, status_filter),
    ):
        if value:
            query = query.where(column == value)
            count_query = count_query.where(column == value)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    query = query.order_by(VulnerabilityFinding.created_at.desc()).offset(offset).limit(page_size)
    findings = (await db.execute(query)).scalars().all()

    return VulnerabilityFindingList(
        findings=[VulnerabilityFindingResponse.model_validate(f) for f in findings], total=total
    )

@router.get("/{finding_id}", response_model=VulnerabilityFindingResponse)
async def get_vulnerability_finding(
    finding_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VulnerabilityFindingResponse:
    finding = (
        await db.execute(select(VulnerabilityFinding).where(VulnerabilityFinding.id == finding_id))
    ).scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vulnerability finding not found")
    return VulnerabilityFindingResponse.model_validate(finding)

@router.post("/remediation/run")
async def run_dependency_fix(
    body: RemediationTriggerRequest,
    _user: User = Depends(get_current_user),
) -> dict:
    """Trigger the Vulnerability Remediation (Custom) agent: dependency-ordered
    fix PR for a repo's open, fixable findings."""
    await _publisher.publish({
        "event_type": "run_vulnerability_dependency_fix",
        "org_login": body.org_login,
        "repo_name": body.repo_name,
    })
    return {"status": "enqueued", "org_login": body.org_login, "repo_name": body.repo_name}

@router.post("/remediation/publish")
async def publish_vulnerability_agent(
    body: RemediationTriggerRequest,
    _user: User = Depends(get_current_user),
) -> dict:
    """Deploy the Vulnerability Remediation agent's scanning workflow into a
    repo via a PR, so it starts feeding real findings to the RCA agent."""
    await _publisher.publish({
        "event_type": "publish_vulnerability_agent",
        "org_login": body.org_login,
        "repo_name": body.repo_name,
    })
    return {"status": "enqueued", "org_login": body.org_login, "repo_name": body.repo_name}

@router.post("/remediation/run-agentic")
async def run_agentic_remediation(
    body: RemediationTriggerRequest,
    _user: User = Depends(get_current_user),
) -> dict:
    """Trigger the deployed agentic remediation workflow (real Claude Code via
    claude-code-action): builds a brief from open findings + Application
    Context + skill files, commits it, and dispatches the workflow.

    If finding_id is set, the brief is scoped to that single finding instead
    of every open finding in the repo -- used by the per-finding "Deploy to
    repository" action."""
    await _publisher.publish({
        "event_type": "run_agentic_remediation",
        "org_login": body.org_login,
        "repo_name": body.repo_name,
        "finding_id": body.finding_id,
    })
    return {"status": "enqueued", "org_login": body.org_login, "repo_name": body.repo_name}

@router.post("/remediation/run-copilot")
async def run_copilot_remediation(
    body: RemediationTriggerRequest,
    _user: User = Depends(get_current_user),
) -> dict:
    """Trigger GitHub Copilot's coding agent (Agent Tasks REST API) to open a
    dependency-ordered fix PR -- no workflow needs to be deployed into the
    repo first, unlike the claude-code-action path."""
    await _publisher.publish({
        "event_type": "run_copilot_remediation",
        "org_login": body.org_login,
        "repo_name": body.repo_name,
    })
    return {"status": "enqueued", "org_login": body.org_login, "repo_name": body.repo_name}
