import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.graph import Graph, GraphEdge, GraphNode
from app.models.organization import Organization
from app.models.user import User
from app.schemas.graph import (
    GraphBuildRequest,
    GraphDetail,
    GraphEdgeResponse,
    GraphList,
    GraphNodeResponse,
    GraphResponse,
)
from app.services.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)

router = APIRouter()

_publisher = SQSPublisher()


async def _assert_org_connected(db: AsyncSession, org_login: str) -> None:
    result = await db.execute(select(Organization).where(Organization.login == org_login))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.post("/{org_login}/repos/{repo_name}/dependency-graph/build", response_model=GraphResponse)
async def build_dependency_graph(
    org_login: str,
    repo_name: str,
    body: GraphBuildRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    """Enqueue a dependency-graph build for a repo. Parsing happens in the worker."""
    await _assert_org_connected(db, org_login)

    graph = Graph(
        org_login=org_login,
        repo_name=repo_name,
        graph_type="dependency",
        ref=body.ref,
        status="pending",
    )
    db.add(graph)
    await db.flush()
    graph_id = graph.id
    await db.commit()

    await _publisher.publish({
        "event_type": "build_dependency_graph",
        "graph_id": str(graph_id),
        "org_login": org_login,
        "repo_name": repo_name,
        "ref": body.ref,
    })

    return GraphResponse.model_validate(graph)


@router.get("/{org_login}/repos/{repo_name}/dependency-graph", response_model=GraphDetail)
async def get_latest_dependency_graph(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphDetail:
    """Return the most recently completed dependency graph for a repo, with nodes/edges."""
    result = await db.execute(
        select(Graph)
        .where(
            Graph.org_login == org_login,
            Graph.repo_name == repo_name,
            Graph.graph_type == "dependency",
            Graph.status == "completed",
        )
        .order_by(Graph.built_at.desc())
        .limit(1)
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed dependency graph found")

    nodes = (await db.execute(select(GraphNode).where(GraphNode.graph_id == graph.id))).scalars().all()
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.graph_id == graph.id))).scalars().all()

    return GraphDetail(
        **GraphResponse.model_validate(graph).model_dump(),
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
    )


@router.get("/{org_login}/repos/{repo_name}/dependency-graph/history", response_model=GraphList)
async def get_dependency_graph_history(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphList:
    """List past dependency-graph build attempts for a repo, most recent first."""
    result = await db.execute(
        select(Graph)
        .where(
            Graph.org_login == org_login,
            Graph.repo_name == repo_name,
            Graph.graph_type == "dependency",
        )
        .order_by(Graph.created_at.desc())
        .limit(50)
    )
    graphs = result.scalars().all()
    return GraphList(graphs=[GraphResponse.model_validate(g) for g in graphs], total=len(graphs))


@router.post("/{org_login}/knowledge-graph/build")
async def build_knowledge_graph(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue a knowledge-graph rebuild — cross-links governance findings, remediation
    failures, and optimization recommendations onto the org's dependency graph nodes."""
    await _assert_org_connected(db, org_login)
    await _publisher.publish({"event_type": "build_knowledge_graph", "org_login": org_login})
    return {"status": "enqueued", "org_login": org_login}


@router.get("/{org_login}/knowledge-graph", response_model=GraphDetail)
async def get_knowledge_graph(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphDetail:
    """Return the org-wide knowledge graph (governance rules, app requirements,
    runtime metrics, and failures cross-linked to dependency-graph nodes)."""
    result = await db.execute(
        select(Graph)
        .where(Graph.org_login == org_login, Graph.graph_type == "knowledge")
        .order_by(Graph.built_at.desc())
        .limit(1)
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No knowledge graph found")

    nodes = list((await db.execute(select(GraphNode).where(GraphNode.graph_id == graph.id))).scalars().all())
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.graph_id == graph.id))).scalars().all()

    # Knowledge-graph edges cross-link to workflow nodes owned by the org's
    # dependency graph (a different graph_id), so fetch those referenced
    # nodes too — otherwise an edge's endpoint is missing from `nodes` and
    # the frontend silently drops the edge.
    own_ids = {n.id for n in nodes}
    referenced_ids = {e.source_node_id for e in edges} | {e.target_node_id for e in edges}
    missing_ids = referenced_ids - own_ids
    if missing_ids:
        extra_nodes = (await db.execute(select(GraphNode).where(GraphNode.id.in_(missing_ids)))).scalars().all()
        nodes.extend(extra_nodes)

    return GraphDetail(
        **GraphResponse.model_validate(graph).model_dump(),
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
    )
