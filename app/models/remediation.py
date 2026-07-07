import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Remediation(Base):
    __tablename__ = "remediations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    workflow_file: Mapped[str] = mapped_column(String(512), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    fixed_yaml: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    suggested_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    likely_code_level: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    code_level_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_branch: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bedrock_model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    security_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    security_findings: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    pr_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pr_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_raised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_trace: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
