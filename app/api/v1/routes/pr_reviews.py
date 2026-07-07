import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.pr_review import PRReview
from app.models.user import User
from app.schemas.pr_review import PRReviewList, PRReviewResponse

router = APIRouter()

@router.get("/", response_model=PRReviewList)
async def list_pr_reviews(
    org_login: str | None = Query(default=None, max_length=255),
    repo_name: str | None = Query(default=None, max_length=255),
    application_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PRReviewList:
    query = select(PRReview)
    count_query = select(func.count()).select_from(PRReview)

    if org_login:
        query = query.where(PRReview.org_login == org_login)
        count_query = count_query.where(PRReview.org_login == org_login)
    if repo_name:
        query = query.where(PRReview.repo_name == repo_name)
        count_query = count_query.where(PRReview.repo_name == repo_name)
    if application_id:
        query = query.where(PRReview.application_id == application_id)
        count_query = count_query.where(PRReview.application_id == application_id)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    query = query.order_by(PRReview.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    reviews = result.scalars().all()

    return PRReviewList(reviews=[PRReviewResponse.model_validate(r) for r in reviews], total=total)

@router.get("/{review_id}", response_model=PRReviewResponse)
async def get_pr_review(
    review_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PRReviewResponse:
    result = await db.execute(select(PRReview).where(PRReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PR review not found")
    return PRReviewResponse.model_validate(review)
