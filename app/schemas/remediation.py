import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class RemediationBase(BaseModel):
    org_login: str
    repo_name: str
    workflow_file: str
    failure_category: str | None = None
    root_cause: str
    bedrock_model: str
    status: str

class RemediationCreate(RemediationBase):
    workflow_run_id: uuid.UUID
    suggested_yaml: str | None = None

class RemediationResponse(RemediationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    suggested_yaml: str | None = None
    original_yaml: str | None = None
    likely_code_level: bool = False
    code_level_reasoning: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    pr_branch: str | None = None
    error_message: str | None = None
    confidence_score: int | None = None
    confidence_reasoning: str | None = None
    security_risk_score: int | None = None
    security_findings: list[str] | None = None
    pr_title: str | None = None
    pr_description: str | None = None
    agent_trace: list[str] | None = None
    created_at: datetime
    updated_at: datetime

class RemediationDetail(RemediationResponse):
    pass

class RemediationList(BaseModel):
    remediations: list[RemediationResponse]
    total: int
    page: int
    page_size: int
