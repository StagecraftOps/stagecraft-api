import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class WorkflowTemplateBase(BaseModel):
    name: str
    description: str | None = None
    template_yaml: str

class WorkflowTemplateCreate(WorkflowTemplateBase):
    pass

class WorkflowTemplateResponse(WorkflowTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class WorkflowTemplateList(BaseModel):
    templates: list[WorkflowTemplateResponse]

class TemplateDiffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str
    workflow_file: str
    template_id: uuid.UUID
    diff_summary: dict
    adoption_score: int
    computed_at: datetime

class TemplateDiffList(BaseModel):
    diffs: list[TemplateDiffResponse]

class PatternClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    pattern_hash: str
    pattern_signature: dict
    occurrence_count: int
    example_workflow_files: list[str]
    computed_at: datetime

class PatternClusterList(BaseModel):
    patterns: list[PatternClusterResponse]

class StandardizationAnalyzeRequest(BaseModel):
    ref: str = "main"
