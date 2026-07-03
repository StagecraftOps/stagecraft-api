"""Internal, service-to-service routes — not part of the public API surface.

Currently exposes search_remediations, the data backend for the
stagecraft-mcp MCP tool of the same name, which the Investigator Agent
(stagecraft-worker) calls to query remediation history during a chat
investigation. Gated by verify_internal_request (a shared-secret header)
in addition to running on a ClusterIP-only service.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_request
from app.db.base import get_db

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
