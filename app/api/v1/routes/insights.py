import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

class SuggestRequest(BaseModel):
    page: str = Field(..., max_length=64)
    metrics: dict

class SuggestResponse(BaseModel):
    suggestion: str | None = None
    severity: str = "ok"

_PROMPT = """You are looking at live operational metrics for a CI/CD platform, from the "{page}" page.

Metrics:
{metrics}

Give the single most important thing to look into or fix right now, based only on these numbers. Requirements:
- ONE short sentence. Under 18 words. Plain text, no markdown, no emojis.
- Reference the actual numbers/names from the metrics above, not generic advice.
- If nothing is concerning, say so in a few words instead of inventing a problem.

Respond with only that one sentence, nothing else."""

_LONG_JOB_WARNING_SECONDS = 900
_LONG_JOB_CRITICAL_SECONDS = 3600

def _classify_severity(page: str, metrics: dict) -> str:
    """Deterministic severity band for the metrics already computed for this
    page -- never LLM-decided, matches this codebase's pattern of
    deterministic classification + LLM narrative-only (see remediation/
    optimization severity fields)."""
    if page == "insights":
        by_sev = metrics.get("open_vulns_by_severity") or {}
        failure_rate = metrics.get("failure_rate") or 0
        if (by_sev.get("critical") or 0) > 0 or failure_rate > 0.5:
            return "critical"
        if (metrics.get("open_vulns_total") or 0) > 0 or failure_rate > 0.2:
            return "warning"
        return "ok"

    if page == "performance":
        durations = [
            entry.get("seconds") or 0
            for entry in (metrics.get("longest_jobs") or []) + (metrics.get("longest_workflows") or [])
        ]
        unassigned = any(
            (r.get("runner") == "no runner assigned" and (r.get("job_count") or 0) > 0)
            for r in (metrics.get("runner_breakdown") or [])
        )
        if any(d > _LONG_JOB_CRITICAL_SECONDS for d in durations):
            return "critical"
        if any(d > _LONG_JOB_WARNING_SECONDS for d in durations) or unassigned:
            return "warning"
        return "ok"

    return "ok"

@router.post("/suggest", response_model=SuggestResponse)
async def suggest(
    body: SuggestRequest,
    _user: User = Depends(get_current_user),
) -> SuggestResponse:
    import boto3

    from app.core.config import settings
    from app.services.bedrock_client import _apply_bedrock_api_key, _bedrock_boto3_kwargs

    severity = _classify_severity(body.page, body.metrics)

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
            **_bedrock_boto3_kwargs(),
        )
        _apply_bedrock_api_key(client)
        prompt = _PROMPT.format(page=body.page, metrics=json.dumps(body.metrics, indent=2, default=str))
        resp = client.converse(
            modelId=settings.BEDROCK_CHAT_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 60, "temperature": 0.2},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip()
        return SuggestResponse(suggestion=text or None, severity=severity)
    except Exception as exc:
        logger.warning("Insight suggestion failed for page=%s: %s", body.page, exc)
        return SuggestResponse(suggestion=None, severity=severity)
