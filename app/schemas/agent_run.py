import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class AgentRunCreate(BaseModel):
    org_login: str = Field(max_length=255)
    repo_name: str | None = Field(default=None, max_length=255)
    agent_name: str = Field(max_length=128)
    github_run_id: str | None = Field(default=None, max_length=64)
    outcome: str = Field(default="success", max_length=64)
    summary: str | None = None
    gaps_found: int = Field(default=0, ge=0)
    prs_opened: list[str] | None = None
    artifacts: list[str] | None = None
    conditions_evaluated: list[dict[str, Any]] | None = None
    evidence: dict[str, Any] | None = None

class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str | None = None
    agent_name: str
    github_run_id: str | None = None
    outcome: str
    summary: str | None = None
    gaps_found: int
    prs_opened: list[str] | None = None
    artifacts: list[str] | None = None
    conditions_evaluated: list[dict[str, Any]] | None = None
    evidence: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

class AgentRunList(BaseModel):
    runs: list[AgentRunResponse]
    total: int

class AgentSummary(BaseModel):
    agent_name: str
    total_runs: int
    last_run_at: datetime | None = None
    last_outcome: str | None = None
    gaps_found: int
    prs_opened: int
    failure_runs: int

class AgentFleetSummary(BaseModel):
    agents: list[AgentSummary]
    total_runs: int
