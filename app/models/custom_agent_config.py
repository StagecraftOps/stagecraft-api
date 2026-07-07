import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class CustomAgentConfig(Base):
    """User-editable configuration for a Custom agent (e.g. the Vulnerability
    Remediation agent that gets published into a repo): a system prompt and a
    set of named "skill files" (markdown/text) that get folded into the
    Bedrock prompt whenever the agent acts, so users can steer its behavior
    without touching code."""

    __tablename__ = "custom_agent_configs"
    __table_args__ = (UniqueConstraint("org_id", "agent_key", "repo_name", name="uq_custom_agent_config_org_key_repo"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # '' = org-wide default config for this agent_key; a real repo name scopes the
    # config to that specific deployed repo (falls back to the '' row when absent).
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_files: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
