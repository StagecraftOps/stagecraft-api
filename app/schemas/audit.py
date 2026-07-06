from datetime import datetime

from pydantic import BaseModel

class ViolationItem(BaseModel):
    author: str | None
    repo_name: str
    pr_number: int
    pr_url: str
    violation: str
    severity: str
    risk_score: int | None
    source: str
    created_at: datetime

class ViolationFeed(BaseModel):
    violations: list[ViolationItem]
    total: int
