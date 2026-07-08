import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class OptimizationRecommendation(Base):
    __tablename__ = "optimization_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_file: Mapped[str] = mapped_column(String(512), nullable=False)
    graph_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    original_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_yaml_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_time_savings_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    pr_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_trace: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimization_recommendations.id", ondelete="CASCADE"), nullable=False
    )
    baseline_critical_path_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    simulated_critical_path_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
