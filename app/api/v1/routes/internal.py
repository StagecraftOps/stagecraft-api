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

_WORKFLOW_MATCH_CLAUSE = (
    "MATCH (w:GraphNode:Workflow) "
    "WHERE ($repo IS NULL OR toLower(w.repo_name) = toLower($repo)) "
    "AND (toLower(w.workflow_file) CONTAINS toLower($wf) OR toLower(w.display_name) CONTAINS toLower($wf)) "
    "WITH w LIMIT $max_matches "
)

_GRAPH_QUERIES = {

    "depends_on": (
        _WORKFLOW_MATCH_CLAUSE
        + "MATCH (j:GraphNode:Job {workflow_file: w.workflow_file})"
        "-[:NEEDS|NEEDS_OUTPUT|USES_REUSABLE|USES_COMPOSITE]->(dep:GraphNode) "
        "RETURN DISTINCT dep.display_name AS name"
    ),

    "depended_on_by": (
        _WORKFLOW_MATCH_CLAUSE
        + "OPTIONAL MATCH (w)-[:WORKFLOW_RUN_TRIGGER]->(triggered:GraphNode) "
        "OPTIONAL MATCH (w)<-[:USES_REUSABLE|USES_COMPOSITE]-(caller:GraphNode) "
        "WITH collect(DISTINCT triggered.display_name) + collect(DISTINCT caller.display_name) AS names "
        "UNWIND names AS name "
        "RETURN DISTINCT name"
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
