from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.pr_review import PRReview
from app.models.user import User
from app.schemas.audit import ViolationFeed, ViolationItem

router = APIRouter()

def _severity(risk_score: int | None) -> str:
    if risk_score is None:
        return "info"
    if risk_score >= 8:
        return "critical"
    if risk_score >= 4:
        return "high"
    if risk_score > 0:
        return "medium"
    return "low"

@router.get("/violations", response_model=ViolationFeed)
async def violation_feed(
    org_login: str | None = Query(default=None, max_length=255),
    author: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViolationFeed:
    query = select(PRReview).where(PRReview.findings.isnot(None))
    if org_login:
        query = query.where(PRReview.org_login == org_login)
    if author:
        query = query.where(PRReview.author == author)
    query = query.order_by(PRReview.created_at.desc())

    reviews = (await db.execute(query)).scalars().all()

    violations: list[ViolationItem] = []
    for review in reviews:
        for finding in review.findings or []:
            violations.append(
                ViolationItem(
                    author=review.author,
                    repo_name=review.repo_name,
                    pr_number=review.pr_number,
                    pr_url=review.pr_url,
                    violation=finding,
                    severity=_severity(review.risk_score),
                    risk_score=review.risk_score,
                    source="peer_review",
                    created_at=review.created_at,
                )
            )
            if len(violations) >= limit:
                break
        if len(violations) >= limit:
            break

    return ViolationFeed(violations=violations, total=len(violations))
