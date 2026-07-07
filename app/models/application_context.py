import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ApplicationContext(Base):
    __tablename__ = "application_contexts"
    __table_args__ = (UniqueConstraint("org_login", "repo_name", name="uq_application_context_org_repo"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    app_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(128), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(128), nullable=True)
    regulatory_scope: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)), nullable=True)
    data_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    team_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
