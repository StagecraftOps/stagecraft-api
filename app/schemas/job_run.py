import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    github_job_id: int
    job_name: str
    status: str
    conclusion: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    runner_name: str | None = None


class JobRunList(BaseModel):
    jobs: list[JobRunResponse]


class CriticalPathResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    total_duration_seconds: int
    critical_path_job_ids: list[uuid.UUID]
    longest_job_id: uuid.UUID | None = None
    computed_at: datetime


class LongestJobEntry(BaseModel):
    job_name: str
    repo_name: str
    workflow_run_id: uuid.UUID
    duration_seconds: int


class LongestWorkflowEntry(BaseModel):
    workflow_name: str
    repo_name: str
    workflow_run_id: uuid.UUID
    duration_seconds: int
