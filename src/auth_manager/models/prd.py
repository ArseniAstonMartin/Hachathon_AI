import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.auth_manager.models.base import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class DocumentExtension(str, enum.Enum):
    DOCX = "docx"
    PDF = "pdf"


class ComparisonJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentFragmentType(str, enum.Enum):
    SECTION = "section"
    CHAPTER = "chapter"
    CLAUSE = "clause"
    SUBCLAUSE = "subclause"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    NOTE = "note"


class DiffType(str, enum.Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    UNCHANGED = "unchanged"


class RiskLevel(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ReportType(str, enum.Enum):
    DOCX = "docx"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(128), nullable=False, unique=True)
    status = Column(
        Enum(TenantStatus, name="tenant_status_enum", values_callable=_enum_values),
        nullable=False,
        server_default=TenantStatus.ACTIVE.value,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_user_id = Column(String(64), nullable=False, unique=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(
        Enum(UserRole, name="user_role_enum", values_callable=_enum_values),
        nullable=False,
        server_default=UserRole.USER.value,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_seen_at = Column(DateTime(timezone=True), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(255), nullable=False)
    extension = Column(
        Enum(DocumentExtension, name="document_extension_enum", values_callable=_enum_values),
        nullable=False,
    )
    storage_path = Column(String(1024), nullable=False)
    checksum = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class DocumentVersionPair(Base):
    __tablename__ = "document_version_pairs"
    __table_args__ = (
        CheckConstraint("old_document_id <> new_document_id", name="ck_pair_documents_distinct"),
        UniqueConstraint(
            "tenant_id",
            "old_document_id",
            "new_document_id",
            name="uq_pair_tenant_old_new",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    new_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ComparisonJob(Base):
    __tablename__ = "comparison_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pair_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_version_pairs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(
        Enum(ComparisonJobStatus, name="comparison_job_status_enum", values_callable=_enum_values),
        nullable=False,
        server_default=ComparisonJobStatus.QUEUED.value,
    )
    current_stage = Column(String(255), nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class DocumentFragment(Base):
    __tablename__ = "document_fragments"
    __table_args__ = (
        UniqueConstraint("document_id", "order_index", name="uq_fragment_document_order"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    fragment_path = Column(String(1024), nullable=False)
    fragment_type = Column(
        Enum(DocumentFragmentType, name="document_fragment_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    raw_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)


class DiffFinding(Base):
    __tablename__ = "diff_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_fragment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_fragments.id", ondelete="SET NULL"),
        nullable=True,
    )
    new_fragment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_fragments.id", ondelete="SET NULL"),
        nullable=True,
    )
    diff_type = Column(
        Enum(DiffType, name="diff_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    semantic_change = Column(Boolean, nullable=False, server_default=text("false"))
    summary = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    risk_level = Column(
        Enum(RiskLevel, name="risk_level_enum", values_callable=_enum_values),
        nullable=False,
    )
    recommendation = Column(Text, nullable=True)


class LegalReference(Base):
    __tablename__ = "legal_references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    diff_finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("diff_findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_title = Column(String(255), nullable=False)
    source_url = Column(String(2048), nullable=False)
    source_platform = Column(String(255), nullable=False)
    hierarchy_level = Column(Integer, nullable=False)
    citation_label = Column(String(255), nullable=False)
    excerpt = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_type = Column(
        Enum(ReportType, name="report_type_enum", values_callable=_enum_values),
        nullable=False,
    )
    storage_path = Column(String(1024), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
