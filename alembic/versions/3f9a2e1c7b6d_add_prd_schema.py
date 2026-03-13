"""Add PRD schema

Revision ID: 3f9a2e1c7b6d
Revises: 0d71a450ee23
Create Date: 2026-03-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3f9a2e1c7b6d"
down_revision: Union[str, Sequence[str], None] = "0d71a450ee23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


tenant_status_enum = postgresql.ENUM(
    "active",
    "disabled",
    name="tenant_status_enum",
    create_type=False,
)
user_role_enum = postgresql.ENUM("user", "admin", name="user_role_enum", create_type=False)
document_extension_enum = postgresql.ENUM(
    "docx",
    "pdf",
    name="document_extension_enum",
    create_type=False,
)
comparison_job_status_enum = postgresql.ENUM(
    "queued",
    "processing",
    "completed",
    "failed",
    name="comparison_job_status_enum",
    create_type=False,
)
document_fragment_type_enum = postgresql.ENUM(
    "section",
    "chapter",
    "clause",
    "subclause",
    "paragraph",
    "table",
    "note",
    name="document_fragment_type_enum",
    create_type=False,
)
diff_type_enum = postgresql.ENUM(
    "added",
    "removed",
    "modified",
    "moved",
    "unchanged",
    name="diff_type_enum",
    create_type=False,
)
risk_level_enum = postgresql.ENUM(
    "green",
    "yellow",
    "red",
    name="risk_level_enum",
    create_type=False,
)
report_type_enum = postgresql.ENUM("docx", name="report_type_enum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    tenant_status_enum.create(bind, checkfirst=True)
    user_role_enum.create(bind, checkfirst=True)
    document_extension_enum.create(bind, checkfirst=True)
    comparison_job_status_enum.create(bind, checkfirst=True)
    document_fragment_type_enum.create(bind, checkfirst=True)
    diff_type_enum.create(bind, checkfirst=True)
    risk_level_enum.create(bind, checkfirst=True)
    report_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            tenant_status_enum,
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            user_role_enum,
            server_default="user",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("extension", document_extension_enum, nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_documents_tenant_id"), "documents", ["tenant_id"], unique=False
    )

    op.create_table(
        "document_version_pairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "old_document_id <> new_document_id",
            name="ck_pair_documents_distinct",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["old_document_id"], ["documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["new_document_id"], ["documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "old_document_id",
            "new_document_id",
            name="uq_pair_tenant_old_new",
        ),
    )
    op.create_index(
        op.f("ix_document_version_pairs_tenant_id"),
        "document_version_pairs",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "comparison_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            comparison_job_status_enum,
            server_default="queued",
            nullable=False,
        ),
        sa.Column("current_stage", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pair_id"], ["document_version_pairs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comparison_jobs_tenant_id"),
        "comparison_jobs",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "document_fragments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fragment_path", sa.String(length=1024), nullable=False),
        sa.Column("fragment_type", document_fragment_type_enum, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "order_index", name="uq_fragment_document_order"
        ),
    )
    op.create_index(
        op.f("ix_document_fragments_tenant_id"),
        "document_fragments",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "diff_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_fragment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("new_fragment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("diff_type", diff_type_enum, nullable=False),
        sa.Column(
            "semantic_change",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["comparison_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["new_fragment_id"], ["document_fragments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["old_fragment_id"], ["document_fragments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_diff_findings_tenant_id"), "diff_findings", ["tenant_id"], unique=False
    )

    op.create_table(
        "legal_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diff_finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_platform", sa.String(length=255), nullable=False),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False),
        sa.Column("citation_label", sa.String(length=255), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["diff_finding_id"], ["diff_findings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["comparison_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legal_references_tenant_id"),
        "legal_references",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "generated_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["comparison_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generated_reports_tenant_id"),
        "generated_reports",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_reports_tenant_id"), table_name="generated_reports")
    op.drop_table("generated_reports")

    op.drop_index(op.f("ix_legal_references_tenant_id"), table_name="legal_references")
    op.drop_table("legal_references")

    op.drop_index(op.f("ix_diff_findings_tenant_id"), table_name="diff_findings")
    op.drop_table("diff_findings")

    op.drop_index(op.f("ix_document_fragments_tenant_id"), table_name="document_fragments")
    op.drop_table("document_fragments")

    op.drop_index(op.f("ix_comparison_jobs_tenant_id"), table_name="comparison_jobs")
    op.drop_table("comparison_jobs")

    op.drop_index(
        op.f("ix_document_version_pairs_tenant_id"),
        table_name="document_version_pairs",
    )
    op.drop_table("document_version_pairs")

    op.drop_index(op.f("ix_documents_tenant_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_table("users")

    op.drop_table("tenants")

    bind = op.get_bind()
    report_type_enum.drop(bind, checkfirst=True)
    risk_level_enum.drop(bind, checkfirst=True)
    diff_type_enum.drop(bind, checkfirst=True)
    document_fragment_type_enum.drop(bind, checkfirst=True)
    comparison_job_status_enum.drop(bind, checkfirst=True)
    document_extension_enum.drop(bind, checkfirst=True)
    user_role_enum.drop(bind, checkfirst=True)
    tenant_status_enum.drop(bind, checkfirst=True)
