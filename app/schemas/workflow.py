import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class WorkflowRunBase(BaseModel):
    github_run_id: int
    github_workflow_id: int
    org_login: str
    repo_name: str
    workflow_name: str
    workflow_file: str
    branch: str
    head_sha: str
    status: str
    conclusion: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    html_url: str

class WorkflowRunCreate(WorkflowRunBase):
    pass

class WorkflowRunResponse(WorkflowRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class WorkflowSummary(BaseModel):
    id: int
    name: str
    path: str
    state: str
    html_url: str
    repo_name: str
    org_login: str

class WorkflowRunList(BaseModel):
    runs: list[WorkflowRunResponse]
    total: int

class WorkflowList(BaseModel):
    workflows: list[WorkflowSummary]
    total: int
