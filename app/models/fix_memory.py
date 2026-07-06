import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class FixMemory(Base):

    __tablename__ = "fix_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_file: Mapped[str] = mapped_column(String(512), nullable=False)
    failure_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    original_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    fixed_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("remediations.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
