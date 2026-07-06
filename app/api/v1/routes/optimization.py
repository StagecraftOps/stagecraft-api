import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.optimization import OptimizationRecommendation, SimulationRun
from app.models.user import User
from app.schemas.optimization import (
    OptimizationAnalyzeRequest,
    OptimizationRecommendationList,
    OptimizationRecommendationResponse,
    SimulationRunResponse,
)
from app.services.sqs_publisher import SQSPublisher

router = APIRouter()

_publisher = SQSPublisher()

@router.post("/orgs/{org_login}/repos/{repo_name}/optimization/analyze")
async def analyze_optimization(
    org_login: str,
    repo_name: str,
    body: OptimizationAnalyzeRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _publisher.publish({
        "event_type": "run_optimization_analysis",
        "org_login": org_login,
        "repo_name": repo_name,
        "workflow_file": body.workflow_file,
        "ref": body.ref,
    })
    return {"status": "enqueued", "org_login": org_login, "repo_name": repo_name}

@router.get("/orgs/{org_login}/repos/{repo_name}/optimization/recommendations", response_model=OptimizationRecommendationList)
async def list_recommendations(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationList:
    result = await db.execute(
        select(OptimizationRecommendation)
        .where(OptimizationRecommendation.org_login == org_login, OptimizationRecommendation.repo_name == repo_name)
        .order_by(OptimizationRecommendation.created_at.desc())
    )
    recs = result.scalars().all()
    return OptimizationRecommendationList(
        recommendations=[OptimizationRecommendationResponse.model_validate(r) for r in recs]
    )

@router.get("/optimization/recommendations/{recommendation_id}/simulation", response_model=SimulationRunResponse)
async def get_simulation(
    recommendation_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.recommendation_id == recommendation_id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return SimulationRunResponse.model_validate(sim)

@router.post("/optimization/recommendations/{recommendation_id}/accept", response_model=OptimizationRecommendationResponse)
async def accept_recommendation(
    recommendation_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationResponse:
    result = await db.execute(
        select(OptimizationRecommendation).where(OptimizationRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    rec.status = "accepted"
    await db.commit()
    await db.refresh(rec)
    return OptimizationRecommendationResponse.model_validate(rec)

@router.post("/optimization/recommendations/{recommendation_id}/reject", response_model=OptimizationRecommendationResponse)
async def reject_recommendation(
    recommendation_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationResponse:
    result = await db.execute(
        select(OptimizationRecommendation).where(OptimizationRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    rec.status = "rejected"
    await db.commit()
    await db.refresh(rec)
    return OptimizationRecommendationResponse.model_validate(rec)
