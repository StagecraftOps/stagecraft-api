"""Internal, service-to-service routes — not part of the public API surface.

Currently exposes search_remediations, the data backend for the
stagecraft-mcp MCP tool of the same name, which the Investigator Agent
(stagecraft-worker) calls to query remediation history during a chat
investigation. Gated by verify_internal_request (a shared-secret header)
in addition to running on a ClusterIP-only service.

Also exposes /graph/query, the GraphRAG backend for the query_graph MCP
tool — a small fixed set of parameterized Cypher traversal shapes (never
free-form Cypher, matching this codebase's "no write tools in agent loops"
posture) so the Investigator can pull structural graph facts alongside its
existing text-search tool. Reads Neo4j directly regardless of GRAPH_BACKEND
(dual-write populates it either way), like search_remediations above this
doesn't filter by org — this deployment is currently single-tenant.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_request
from app.db.base import get_db
from app.db.neo4j import async_neo4j_driver

router = APIRouter()

_MAX_RESULTS = 20


class RemediationSearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    repo_name: str | None = None
    failure_category: str | None = None
    since_days: int | None = Field(default=None, ge=1, le=365)
    limit: int = Field(default=8, ge=1, le=_MAX_RESULTS)


class RemediationSearchResult(BaseModel):
    remediation_id: str
    repo_name: str
    workflow_file: str
    failure_category: str | None
    root_cause: str
    confidence_score: int | None
    status: str
    created_at: datetime
    relevance: float | None = None


class RemediationSearchResponse(BaseModel):
    results: list[RemediationSearchResult]


@router.post("/remediations/search", response_model=RemediationSearchResponse)
async def search_remediations(
    req: RemediationSearchRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_request),
) -> RemediationSearchResponse:
    """Search remediation history by filters and/or semantic similarity.

    With `query` set: embeds it and ranks by pgvector cosine similarity
    against log_embeddings, joined back to remediations for the structured
    fields. Without `query`: plain filtered SQL over remediations, newest
    first — used when the investigator already knows exactly which
    repo/category/time window it wants, with no need for semantic ranking.
    """
    filters = ["1=1"]
    params: dict = {"limit": req.limit}
    if req.repo_name:
        filters.append("r.repo_name = :repo_name")
        params["repo_name"] = req.repo_name
    if req.failure_category:
        filters.append("r.failure_category = :failure_category")
        params["failure_category"] = req.failure_category
    if req.since_days:
        params["since"] = datetime.now(timezone.utc) - timedelta(days=req.since_days)
        filters.append("r.created_at >= :since")
    where_clause = " AND ".join(filters)

    if req.query:
        from app.services.embeddings import embed_text, to_pgvector

        qvec = to_pgvector(embed_text(req.query))
        params["qvec"] = qvec
        rows = (
            await db.execute(
                text(
                    f"""
                    SELECT r.id, r.repo_name, r.workflow_file, r.failure_category,
                           r.root_cause, r.confidence_score, r.status, r.created_at,
                           1 - (e.embedding <=> CAST(:qvec AS vector)) AS score
                    FROM log_embeddings e
                    JOIN remediations r ON r.id = e.source_id
                    WHERE e.source_type = 'remediation' AND {where_clause}
                    ORDER BY e.embedding <=> CAST(:qvec AS vector)
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).fetchall()
    else:
        rows = (
            await db.execute(
                text(
                    f"""
                    SELECT r.id, r.repo_name, r.workflow_file, r.failure_category,
                           r.root_cause, r.confidence_score, r.status, r.created_at,
                           NULL AS score
                    FROM remediations r
                    WHERE {where_clause}
                    ORDER BY r.created_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).fetchall()

    return RemediationSearchResponse(
        results=[
            RemediationSearchResult(
                remediation_id=str(row.id),
                repo_name=row.repo_name,
                workflow_file=row.workflow_file,
                failure_category=row.failure_category,
                root_cause=row.root_cause,
                confidence_score=row.confidence_score,
                status=row.status,
                created_at=row.created_at,
                relevance=round(float(row.score), 3) if row.score is not None else None,
            )
            for row in rows
        ]
    )


_MAX_WORKFLOW_MATCHES = 5

# Anchor clause shared by every relationship below: the LLM calling this only
# has whatever colloquial name the user typed ("ci-auth-service"), never the
# exact workflow_file path (".github/workflows/ci-auth-service.yml") or
# necessarily the exact repo_name -- an exact-equality match against those
# was a real dead end (verified live: a real question returned zero results
# because the model's guess didn't match either field byte-for-byte). Fuzzy
# CONTAINS against both workflow_file and display_name, repo optional,
# capped at _MAX_WORKFLOW_MATCHES matching workflows so an over-broad term
# doesn't silently aggregate half the org's dependency graph into one answer.
_WORKFLOW_MATCH_CLAUSE = (
    "MATCH (w:GraphNode:Workflow) "
    "WHERE ($repo IS NULL OR toLower(w.repo_name) = toLower($repo)) "
    "AND (toLower(w.workflow_file) CONTAINS toLower($wf) OR toLower(w.display_name) CONTAINS toLower($wf)) "
    "WITH w LIMIT $max_matches "
)

_GRAPH_QUERIES = {
    "depends_on": (
        _WORKFLOW_MATCH_CLAUSE
        + "MATCH (w)-[:NEEDS|NEEDS_OUTPUT|USES_REUSABLE|USES_COMPOSITE]->(dep:GraphNode) "
        "RETURN DISTINCT dep.display_name AS name"
    ),
    "depended_on_by": (
        _WORKFLOW_MATCH_CLAUSE
        + "MATCH (w)<-[:NEEDS|USES_REUSABLE|USES_COMPOSITE|WORKFLOW_RUN_TRIGGER|REPOSITORY_DISPATCH]-(dep:GraphNode) "
        "RETURN DISTINCT dep.display_name AS name"
    ),
    "governance": (
        _WORKFLOW_MATCH_CLAUSE
        + "MATCH (rule:GraphNode:GovernanceRule)-[:GOVERNS]->(w) "
        "RETURN DISTINCT rule.display_name AS name"
    ),
    "failures": (
        _WORKFLOW_MATCH_CLAUSE
        + "MATCH (fail:GraphNode:Failure)-[:CAUSED_BY]->(w) "
        "RETURN DISTINCT fail.display_name AS name"
    ),
}


class GraphQueryRequest(BaseModel):
    repo_name: str | None = None
    workflow_file: str
    relationship: str = Field(default="depends_on")


class GraphQueryResponse(BaseModel):
    relationship: str
    items: list[str]


@router.post("/graph/query", response_model=GraphQueryResponse)
async def query_graph(
    req: GraphQueryRequest,
    _: None = Depends(verify_internal_request),
) -> GraphQueryResponse:
    """GraphRAG backend for the Investigator's query_graph tool.

    relationship='depends_on': what this workflow calls (reusable workflows,
    composite actions, jobs it needs). 'depended_on_by': what triggers/calls
    it. 'governance': governance rules already linked to it. 'failures':
    failure history connected to it. Deliberately a fixed lookup, not
    free-form Cypher, even though the caller is a trusted internal service.

    workflow_file is matched fuzzily (case-insensitive substring against
    both workflow_file and display_name) and repo_name is optional -- the
    caller only ever has a colloquial name to work with, never necessarily
    the exact repo-root-relative path.
    """
    cypher = _GRAPH_QUERIES.get(req.relationship)
    if not cypher:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"relationship must be one of {sorted(_GRAPH_QUERIES)}",
        )

    async with async_neo4j_driver.session() as neo_session:
        result = await neo_session.run(
            cypher, repo=req.repo_name, wf=req.workflow_file, max_matches=_MAX_WORKFLOW_MATCHES,
        )
        items = [record["name"] async for record in result if record["name"]]

    return GraphQueryResponse(relationship=req.relationship, items=items)
