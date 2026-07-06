import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import get_db
from app.db.neo4j import async_neo4j_driver
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

_DEPENDENCY_NODE_TYPES = ["workflow", "job", "reusable_workflow", "composite_action"]
_KNOWLEDGE_NODE_TYPES = ["governance_rule", "failure", "runtime_metric"]

_ORG_WIDE_DECLARABLE_TYPES = ["service", "external_repo"]

_DEPENDENCY_REL_TYPES = [
    "NEEDS", "NEEDS_OUTPUT", "MATRIX_FANOUT", "USES_REUSABLE",
    "USES_COMPOSITE", "ORCHESTRATOR_SERVICE_DEP", "REPOSITORY_DISPATCH",
    "WORKFLOW_RUN_TRIGGER",
]
_KNOWLEDGE_REL_TYPES = ["GOVERNS", "CAUSED_BY", "MEASURED_BY"]

_REL_TYPE_TO_EDGE_TYPE = {
    "NEEDS": "needs",
    "NEEDS_OUTPUT": "needs_output",
    "MATRIX_FANOUT": "matrix_fanout",
    "USES_REUSABLE": "uses_reusable",
    "USES_COMPOSITE": "uses_composite",
    "ORCHESTRATOR_SERVICE_DEP": "orchestrator_service_dep",
    "REPOSITORY_DISPATCH": "repository_dispatch",
    "WORKFLOW_RUN_TRIGGER": "workflow_run_trigger",
    "GOVERNS": "governs",
    "CAUSED_BY": "caused_by",
    "MEASURED_BY": "measured_by",
}

def _neo4j_node_to_response(n) -> GraphNodeResponse:
    return GraphNodeResponse(
        id=uuid.UUID(n["id"]),
        node_type=n["node_type"],
        external_key=n["external_key"],
        display_name=n["display_name"],
        workflow_file=n.get("workflow_file"),
        job_id=n.get("job_id"),
        node_metadata=json.loads(n["metadata_json"]) if n.get("metadata_json") else None,
    )

def _neo4j_edge_to_response(e, source_id: str, target_id: str) -> GraphEdgeResponse:
    return GraphEdgeResponse(
        id=uuid.UUID(e["id"]),
        source_node_id=uuid.UUID(source_id),
        target_node_id=uuid.UUID(target_id),
        edge_type=_REL_TYPE_TO_EDGE_TYPE.get(e.type, e.type.lower()),
        confidence=e.get("confidence", "certain"),
        edge_metadata=json.loads(e["metadata_json"]) if e.get("metadata_json") else None,
    )

async def _fetch_from_neo4j(
    org_login: str, repo_name: str | None, graph_type: str
) -> tuple[list[GraphNodeResponse], list[GraphEdgeResponse]]:
    async with async_neo4j_driver.session() as neo_session:
        if graph_type == "dependency":
            node_query = (
                "MATCH (n:GraphNode {org_login: $org}) "
                "WHERE (n.repo_name = $repo AND n.node_type IN $types) "
                "   OR ($repo IN coalesce(n.declared_by_repos, []) AND n.node_type IN $org_wide_types) "
                "RETURN n"
            )
            params = {
                "org": org_login, "repo": repo_name,
                "types": _DEPENDENCY_NODE_TYPES, "org_wide_types": _ORG_WIDE_DECLARABLE_TYPES,
            }
            edge_query = (
                "MATCH (s:GraphNode)-[e]->(t:GraphNode) "
                "WHERE e.org_login = $org AND e.repo_name = $repo AND type(e) IN $rel_types "
                "RETURN e, s, t"
            )
            edge_params = {"org": org_login, "repo": repo_name, "rel_types": _DEPENDENCY_REL_TYPES}
        else:
            node_query = (
                "MATCH (n:GraphNode {org_login: $org}) WHERE n.node_type IN $types RETURN n"
            )
            params = {"org": org_login, "types": _KNOWLEDGE_NODE_TYPES}
            edge_query = (
                "MATCH (s:GraphNode)-[e]->(t:GraphNode) "
                "WHERE e.org_login = $org AND type(e) IN $rel_types "
                "RETURN e, s, t"
            )
            edge_params = {"org": org_login, "rel_types": _KNOWLEDGE_REL_TYPES}

        result = await neo_session.run(node_query, params)
        primary_nodes = {record["n"]["id"]: record["n"] async for record in result}

        if not primary_nodes:
            return [], []

        edge_result = await neo_session.run(edge_query, edge_params)
        extra_nodes: dict[str, object] = {}
        edge_responses: list[GraphEdgeResponse] = []
        async for record in edge_result:
            s, t = record["s"], record["t"]
            if s["id"] not in primary_nodes:
                extra_nodes[s["id"]] = s
            if t["id"] not in primary_nodes:
                extra_nodes[t["id"]] = t
            edge_responses.append(_neo4j_edge_to_response(record["e"], s["id"], t["id"]))

        all_nodes = {**primary_nodes, **extra_nodes}
        return [_neo4j_node_to_response(n) for n in all_nodes.values()], edge_responses

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

    if settings.GRAPH_BACKEND == "neo4j":
        node_responses, edge_responses = await _fetch_from_neo4j(org_login, repo_name, "dependency")
    else:
        nodes = (await db.execute(select(GraphNode).where(GraphNode.graph_id == graph.id))).scalars().all()
        edges = (await db.execute(select(GraphEdge).where(GraphEdge.graph_id == graph.id))).scalars().all()
        node_responses = [GraphNodeResponse.model_validate(n) for n in nodes]
        edge_responses = [GraphEdgeResponse.model_validate(e) for e in edges]

    return GraphDetail(
        **GraphResponse.model_validate(graph).model_dump(),
        nodes=node_responses,
        edges=edge_responses,
    )

@router.get("/{org_login}/repos/{repo_name}/dependency-graph/history", response_model=GraphList)
async def get_dependency_graph_history(
    org_login: str,
    repo_name: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphList:
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
    await _assert_org_connected(db, org_login)
    await _publisher.publish({"event_type": "build_knowledge_graph", "org_login": org_login})
    return {"status": "enqueued", "org_login": org_login}

@router.get("/{org_login}/knowledge-graph", response_model=GraphDetail)
async def get_knowledge_graph(
    org_login: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphDetail:
    result = await db.execute(
        select(Graph)
        .where(Graph.org_login == org_login, Graph.graph_type == "knowledge")
        .order_by(Graph.built_at.desc())
        .limit(1)
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No knowledge graph found")

    if settings.GRAPH_BACKEND == "neo4j":
        node_responses, edge_responses = await _fetch_from_neo4j(org_login, None, "knowledge")
    else:
        nodes = list((await db.execute(select(GraphNode).where(GraphNode.graph_id == graph.id))).scalars().all())
        edges = (await db.execute(select(GraphEdge).where(GraphEdge.graph_id == graph.id))).scalars().all()

        own_ids = {n.id for n in nodes}
        referenced_ids = {e.source_node_id for e in edges} | {e.target_node_id for e in edges}
        missing_ids = referenced_ids - own_ids
        if missing_ids:
            extra_nodes = (await db.execute(select(GraphNode).where(GraphNode.id.in_(missing_ids)))).scalars().all()
            nodes.extend(extra_nodes)

        node_responses = [GraphNodeResponse.model_validate(n) for n in nodes]
        edge_responses = [GraphEdgeResponse.model_validate(e) for e in edges]

    return GraphDetail(
        **GraphResponse.model_validate(graph).model_dump(),
        nodes=node_responses,
        edges=edge_responses,
    )
