import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_token
from app.db.base import get_db
from app.models.graph import Graph
from app.models.optimization import OptimizationRecommendation, SimulationRun
from app.models.user import User
from app.schemas.optimization import (
    OptimizationAnalyzeRequest,
    OptimizationRecommendationList,
    OptimizationRecommendationResponse,
    SimulationRunResponse,
)
from app.services.github import GitHubService
from app.services.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)

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

async def _get_github_token(org_login: str, user: User) -> str:
    from app.services.github_app import get_installation_token_for_org, github_app_configured

    if github_app_configured():
        return await get_installation_token_for_org(org_login)
    return decrypt_token(user.access_token_encrypted)

@router.get("/orgs/{org_login}/repos/{repo_name}/optimization/recommendations", response_model=OptimizationRecommendationList)
async def list_recommendations(
    org_login: str,
    repo_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationList:
    result = await db.execute(
        select(OptimizationRecommendation)
        .where(OptimizationRecommendation.org_login == org_login, OptimizationRecommendation.repo_name == repo_name)
        .order_by(OptimizationRecommendation.created_at.desc())
    )
    recs = result.scalars().all()

    responses = [OptimizationRecommendationResponse.model_validate(r) for r in recs]

    # original_yaml is normally captured at analysis time (see optimization.py's
    # worker task) and returned as-is above via model_validate. This fallback only
    # covers recommendations created before that snapshot existed -- best-effort,
    # and may not match what the LLM actually saw if the file has since drifted.
    stale_recs = [(rec, response) for rec, response in zip(recs, responses) if not rec.original_yaml]
    if stale_recs:
        graph_ids = {rec.graph_id for rec, _ in stale_recs}
        graph_result = await db.execute(select(Graph).where(Graph.id.in_(graph_ids)))
        graphs: dict[uuid.UUID, Graph] = {g.id: g for g in graph_result.scalars().all()}

        try:
            token = await _get_github_token(org_login, user)
        except Exception as exc:
            logger.warning("Could not obtain GitHub token for original_yaml fallback fetch: %s", exc)
            token = None

        if token:
            github = GitHubService(token)
            try:
                for rec, response in stale_recs:
                    graph = graphs.get(rec.graph_id)
                    ref = graph.ref if graph and graph.ref else "main"
                    try:
                        response.original_yaml = await github.get_workflow_file(
                            org_login, repo_name, rec.workflow_file, ref
                        )
                    except Exception as exc:
                        logger.warning(
                            "Could not fetch fallback original_yaml for recommendation %s: %s", rec.id, exc
                        )
            finally:
                await github.aclose()

    return OptimizationRecommendationList(recommendations=responses)

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizationRecommendationResponse:
    result = await db.execute(
        select(OptimizationRecommendation).where(OptimizationRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    if rec.status == "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PR already raised")
    if not rec.proposed_yaml_diff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No suggested workflow YAML available for this recommendation",
        )

    graph_result = await db.execute(select(Graph).where(Graph.id == rec.graph_id))
    graph = graph_result.scalar_one_or_none()
    base_ref = graph.ref if graph and graph.ref else "main"

    token = await _get_github_token(rec.org_login, user)
    github = GitHubService(token)
    fix_branch = f"stagecraft/optimize-{str(rec.id)[:8]}"
    try:
        current_sha = await github.get_file_sha(rec.org_login, rec.repo_name, rec.workflow_file, base_ref)

        if rec.original_yaml is not None:
            live_content = await github.get_workflow_file(rec.org_login, rec.repo_name, rec.workflow_file, base_ref)
            if live_content != rec.original_yaml:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"{rec.workflow_file} has changed since this recommendation was analyzed. "
                        "Re-run Analyze to get an up-to-date suggestion before accepting."
                    ),
                )

        base_sha = await github.get_branch_head_sha(rec.org_login, rec.repo_name, base_ref)
        await github.create_fix_branch(rec.org_login, rec.repo_name, base_sha, fix_branch)

        await github.commit_fix(
            owner=rec.org_login,
            repo=rec.repo_name,
            branch=fix_branch,
            path=rec.workflow_file,
            content=rec.proposed_yaml_diff,
            message=f"perf: Stagecraft-suggested {rec.recommendation_type} optimization for {rec.workflow_file}",
            current_sha=current_sha,
        )

        savings_line = (
            f"Estimated time savings: ~{rec.estimated_time_savings_seconds}s per run.\n\n"
            if rec.estimated_time_savings_seconds
            else ""
        )
        pr_body = (
            f"## Optimization\n{rec.description}\n\n{savings_line}"
            "This change was suggested by Stagecraft (AWS Bedrock - Claude) based on real "
            "dependency-graph and job-timing analysis. Please review before merging.\n\n"
            "> Generated by Stagecraft"
        )
        pr_data = await github.create_pr(
            owner=rec.org_login,
            repo=rec.repo_name,
            head=fix_branch,
            base=base_ref,
            title=f"perf: {rec.recommendation_type} optimization for {rec.workflow_file}",
            body=pr_body,
        )

        rec.pr_url = pr_data.get("html_url")
        rec.pr_number = pr_data.get("number")
        rec.pr_branch = fix_branch
        rec.status = "accepted"
        await db.commit()
        await db.refresh(rec)
        return OptimizationRecommendationResponse.model_validate(rec)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to raise PR for optimization recommendation %s: %s", recommendation_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create PR on GitHub.")
    finally:
        await github.aclose()

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
