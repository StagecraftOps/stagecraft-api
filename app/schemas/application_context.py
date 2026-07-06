import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class ApplicationContextBase(BaseModel):
    app_name: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=128)
    framework: str | None = Field(default=None, max_length=128)
    regulatory_scope: list[str] | None = None
    data_classification: str | None = Field(default=None, max_length=64)
    risk_tier: str | None = Field(default=None, max_length=32)
    team_owner: str | None = Field(default=None, max_length=255)
    security_contact: str | None = Field(default=None, max_length=255)
    notes: str | None = None

class ApplicationContextCreate(ApplicationContextBase):
    org_login: str = Field(max_length=255)
    repo_name: str = Field(max_length=255)
    source: str = Field(default="manual", max_length=32)
    raw_content: str | None = None

class ApplicationContextResponse(ApplicationContextBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str
    source: str
    created_at: datetime
    updated_at: datetime

class ApplicationContextList(BaseModel):
    contexts: list[ApplicationContextResponse]
    total: int
