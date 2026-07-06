import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class GovernanceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    doc_type: str
    title: str
    source_filename: str | None = None
    structured_requirements: dict | None = None
    created_at: datetime
    updated_at: datetime

class GovernanceDocumentList(BaseModel):
    documents: list[GovernanceDocumentResponse]

class ComplianceFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str
    workflow_file: str
    governance_document_id: uuid.UUID | None = None
    requirement_id: str
    status: str
    finding_detail: str
    remediation_suggestion: str | None = None
    severity: str
    computed_at: datetime

class ComplianceFindingList(BaseModel):
    findings: list[ComplianceFindingResponse]

class GovernanceAnalyzeRequest(BaseModel):
    mode: str
    ref: str = "main"
    framework: str | None = None
    document_id: uuid.UUID | None = None
