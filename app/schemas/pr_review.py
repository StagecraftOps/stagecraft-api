import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class PRReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str
    pr_number: int
    pr_url: str
    author: str | None = None
    risk_score: int | None = None
    findings: list[str] | None = None
    review_summary: str | None = None
    status: str
    agent_trace: list[str] | None = None
    created_at: datetime
    updated_at: datetime

class PRReviewList(BaseModel):
    reviews: list[PRReviewResponse]
    total: int
