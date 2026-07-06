import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class GraphNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_type: str
    external_key: str
    display_name: str
    workflow_file: str | None = None
    job_id: str | None = None
    node_metadata: dict | None = None

class GraphEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: str
    confidence: str
    edge_metadata: dict | None = None

class GraphResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_login: str
    repo_name: str | None = None
    graph_type: str
    ref: str | None = None
    status: str
    node_count: int
    edge_count: int
    error_message: str | None = None
    built_at: datetime | None = None
    created_at: datetime

class GraphDetail(GraphResponse):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]

class GraphList(BaseModel):
    graphs: list[GraphResponse]
    total: int

class GraphBuildRequest(BaseModel):
    ref: str = "main"
