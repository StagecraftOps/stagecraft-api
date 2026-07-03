import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceDocument(Base):
    """FR-5/FR-6: an uploaded governance policy or application-profile document.

    doc_type='governance_policy' -> compared by the Governance Agent (FR-5).
    doc_type='app_profile' -> compared by the Compliance Agent for
    application-aware checks (FR-6, e.g. "this app handles PHI, HIPAA applies").
    """
    __tablename__ = "governance_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_requirements: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ComplianceFinding(Base):
    """A single control-presence finding, produced by either the Compliance
    Agent (framework-based, governance_document_id NULL) or the Governance
    Agent (document-based, governance_document_id set)."""
    __tablename__ = "compliance_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_file: Mapped[str] = mapped_column(String(512), nullable=False)
    governance_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("governance_documents.id", ondelete="CASCADE"), nullable=True
    )
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # compliant|gap|not_applicable
    finding_detail: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
