import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class K8sLogEvent(BaseModel):
    cluster_name: str
    namespace: str
    pod_name: str
    container_name: str
    log_lines: list[str]
    timestamp: str = ""


class K8sAnalysisResult(BaseModel):
    id: str
    cluster_name: str
    namespace: str
    pod_name: str
    status: str
    root_cause: str | None = None
    suggested_fix: str | None = None
    fix_type: str | None = None
    source_repo: str | None = None
    pr_url: str | None = None
    created_at: str


_store: dict[str, dict] = {}


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_pod_logs(
    event: K8sLogEvent,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Beta: Accept Kubernetes pod logs for AI-based root cause analysis.
    Returns an analysis ID — poll GET /k8s-remediation/{id} for results.
    This endpoint is intentionally async (202) since Bedrock analysis takes time.
    """
    if len(event.log_lines) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 500 log lines per request",
        )

    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    _store[analysis_id] = {
        "id": analysis_id,
        "cluster_name": event.cluster_name,
        "namespace": event.namespace,
        "pod_name": event.pod_name,
        "container_name": event.container_name,
        "status": "analyzing",
        "root_cause": None,
        "suggested_fix": None,
        "fix_type": None,
        "source_repo": None,
        "pr_url": None,
        "created_at": now,
        "_log_lines": event.log_lines,
    }

    logger.info(
        "K8s remediation analysis started: %s (pod=%s/%s)",
        analysis_id, event.namespace, event.pod_name,
    )

    return {"analysis_id": analysis_id, "status": "analyzing", "created_at": now}


@router.get("/{analysis_id}", response_model=K8sAnalysisResult)
async def get_k8s_analysis(
    analysis_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> K8sAnalysisResult:
    """Return the current status of a K8s pod log analysis."""
    record = _store.get(analysis_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return K8sAnalysisResult(
        id=record["id"],
        cluster_name=record["cluster_name"],
        namespace=record["namespace"],
        pod_name=record["pod_name"],
        status=record["status"],
        root_cause=record.get("root_cause"),
        suggested_fix=record.get("suggested_fix"),
        fix_type=record.get("fix_type"),
        source_repo=record.get("source_repo"),
        pr_url=record.get("pr_url"),
        created_at=record["created_at"],
    )


@router.get("/", response_model=list[K8sAnalysisResult])
async def list_k8s_analyses(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[K8sAnalysisResult]:
    """List all K8s pod log analyses for this session."""
    return [
        K8sAnalysisResult(
            id=r["id"],
            cluster_name=r["cluster_name"],
            namespace=r["namespace"],
            pod_name=r["pod_name"],
            status=r["status"],
            root_cause=r.get("root_cause"),
            suggested_fix=r.get("suggested_fix"),
            fix_type=r.get("fix_type"),
            source_repo=r.get("source_repo"),
            pr_url=r.get("pr_url"),
            created_at=r["created_at"],
        )
        for r in sorted(_store.values(), key=lambda x: x["created_at"], reverse=True)
    ]
