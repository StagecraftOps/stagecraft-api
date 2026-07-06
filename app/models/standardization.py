import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

class TemplateDiff(Base):
    __tablename__ = "template_diffs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_file: Mapped[str] = mapped_column(String(512), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="CASCADE"), nullable=False
    )
    diff_summary: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    adoption_score: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class PatternCluster(Base):
    __tablename__ = "pattern_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pattern_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pattern_signature: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    example_workflow_files: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
