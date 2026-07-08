import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class OptimizationRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str
    workflow_file: str
    graph_id: uuid.UUID
    recommendation_type: str
    description: str
    original_yaml: str | None = None
    proposed_yaml_diff: str | None = None
    estimated_time_savings_seconds: int
    confidence_score: int
    status: str
    pr_url: str | None = None
    pr_number: int | None = None
    pr_branch: str | None = None
    agent_trace: list[str] | None = None
    created_at: datetime
    updated_at: datetime

class OptimizationRecommendationList(BaseModel):
    recommendations: list[OptimizationRecommendationResponse]

class SimulationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recommendation_id: uuid.UUID
    baseline_critical_path_seconds: int
    simulated_critical_path_seconds: int
    delta_seconds: int
    computed_at: datetime

class OptimizationAnalyzeRequest(BaseModel):
    workflow_file: str
    ref: str = "main"
