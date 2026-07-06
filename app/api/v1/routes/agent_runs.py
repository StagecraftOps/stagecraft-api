import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_internal_request
from app.db.base import get_db
from app.models.agent_run import AgentRun
from app.models.user import User
from app.schemas.agent_run import (
    AgentFleetSummary,
    AgentRunCreate,
    AgentRunList,
    AgentRunResponse,
    AgentSummary,
)
from app.services.sqs_publisher import SQSPublisher

router = APIRouter()

_publisher = SQSPublisher()

_TRIGGERABLE = {
    "drift_detector": "run_drift_detection",
    "compliance_watchdog": "run_compliance_watchdog",
}

KNOWN_AGENTS = [
    "failure_rca",
    "peer_review",
    "compliance",
    "governance",
    "performance_optimization",
    "drift_detector",
    "compliance_watchdog",
    "vulnerability_remediation",
    "audit_evidence",
]

@router.post("/", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def report_agent_run(
    payload: AgentRunCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_request),
) -> AgentRunResponse:
    run = AgentRun(**payload.model_dump())
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return AgentRunResponse.model_validate(run)

@router.post("/{agent_name}/trigger")
async def trigger_agent(
    agent_name: str,
    org_login: str = Query(..., max_length=255),
    repo_name: str = Query(..., max_length=255),
    ref: str = Query(default="main", max_length=255),
    _user: User = Depends(get_current_user),
) -> dict:
    event_type = _TRIGGERABLE.get(agent_name)
    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent '{agent_name}' cannot be triggered on demand.",
        )
    await _publisher.publish({
        "event_type": event_type,
        "org_login": org_login,
        "repo_name": repo_name,
        "ref": ref,
    })
    return {"status": "enqueued", "agent_name": agent_name, "org_login": org_login, "repo_name": repo_name}

@router.get("/summary", response_model=AgentFleetSummary)
async def agent_fleet_summary(
    org_login: str | None = Query(default=None, max_length=255),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentFleetSummary:
    base = select(
        AgentRun.agent_name,
        func.count().label("total_runs"),
        func.max(AgentRun.created_at).label("last_run_at"),
        func.coalesce(func.sum(AgentRun.gaps_found), 0).label("gaps_found"),
        func.coalesce(
            func.sum(func.coalesce(func.array_length(AgentRun.prs_opened, 1), 0)), 0
        ).label("prs_opened"),
        func.coalesce(
            func.sum(case((AgentRun.outcome == "failure", 1), else_=0)), 0
        ).label("failure_runs"),
    )
    if org_login:
        base = base.where(AgentRun.org_login == org_login)
    base = base.group_by(AgentRun.agent_name)

    rows = {r.agent_name: r for r in (await db.execute(base)).all()}

    last_outcomes: dict[str, str] = {}
    for name in rows:
        q = (
            select(AgentRun.outcome)
            .where(AgentRun.agent_name == name)
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        if org_login:
            q = q.where(AgentRun.org_login == org_login)
        outcome = (await db.execute(q)).scalar_one_or_none()
        if outcome:
            last_outcomes[name] = outcome

    agents: list[AgentSummary] = []
    names = list(dict.fromkeys([*KNOWN_AGENTS, *rows.keys()]))
    total_runs = 0
    for name in names:
        r = rows.get(name)
        runs = int(r.total_runs) if r else 0
        total_runs += runs
        agents.append(
            AgentSummary(
                agent_name=name,
                total_runs=runs,
                last_run_at=r.last_run_at if r else None,
                last_outcome=last_outcomes.get(name),
                gaps_found=int(r.gaps_found) if r else 0,
                prs_opened=int(r.prs_opened) if r else 0,
                failure_runs=int(r.failure_runs) if r else 0,
            )
        )
    return AgentFleetSummary(agents=agents, total_runs=total_runs)

@router.get("/", response_model=AgentRunList)
async def list_agent_runs(
    org_login: str | None = Query(default=None, max_length=255),
    agent_name: str | None = Query(default=None, max_length=128),
    repo_name: str | None = Query(default=None, max_length=255),
    outcome: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunList:
    query = select(AgentRun)
    count_query = select(func.count()).select_from(AgentRun)

    for column, value in (
        (AgentRun.org_login, org_login),
        (AgentRun.agent_name, agent_name),
        (AgentRun.repo_name, repo_name),
        (AgentRun.outcome, outcome),
    ):
        if value:
            query = query.where(column == value)
            count_query = count_query.where(column == value)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    query = query.order_by(AgentRun.created_at.desc()).offset(offset).limit(page_size)
    runs = (await db.execute(query)).scalars().all()

    return AgentRunList(runs=[AgentRunResponse.model_validate(r) for r in runs], total=total)

@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return AgentRunResponse.model_validate(run)
