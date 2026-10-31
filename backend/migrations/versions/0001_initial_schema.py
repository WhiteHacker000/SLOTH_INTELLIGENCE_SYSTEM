"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-01 00:20:52.723364
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("html_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index(
        op.f("ix_repositories_full_name"), "repositories", ["full_name"], unique=True
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("rationale", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "trade_offs", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "proposed", "accepted", "rejected", "unresolved", name="decision_status"
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extraction_model", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_decisions_repository_id"), "decisions", ["repository_id"], unique=False
    )
    op.create_index(op.f("ix_decisions_status"), "decisions", ["status"], unique=False)
    op.create_table(
        "discussions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("issue", "pull_request", name="discussion_kind"),
            nullable=False,
        ),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "number", name="uq_discussion_number"),
    )
    op.create_index(
        op.f("ix_discussions_repository_id"),
        "discussions",
        ["repository_id"],
        unique=False,
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discussion_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("issue_comment", "review_comment", "review", name="comment_kind"),
            nullable=False,
        ),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["discussion_id"], ["discussions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "github_id", name="uq_comment_source"),
    )
    op.create_index(
        op.f("ix_comments_discussion_id"), "comments", ["discussion_id"], unique=False
    )
    op.create_table(
        "decision_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("discussion_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["discussion_id"], ["discussions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_decision_evidence_decision_id"),
        "decision_evidence",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decision_evidence_discussion_id"),
        "decision_evidence",
        ["discussion_id"],
        unique=False,
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discussion_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["discussion_id"], ["discussions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "discussion_id",
            "comment_id",
            "ordinal",
            name="uq_chunk_position",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        op.f("ix_document_chunks_comment_id"),
        "document_chunks",
        ["comment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_discussion_id"),
        "document_chunks",
        ["discussion_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_chunks_discussion_id"), table_name="document_chunks"
    )
    op.drop_index(op.f("ix_document_chunks_comment_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index(
        op.f("ix_decision_evidence_discussion_id"), table_name="decision_evidence"
    )
    op.drop_index(
        op.f("ix_decision_evidence_decision_id"), table_name="decision_evidence"
    )
    op.drop_table("decision_evidence")
    op.drop_index(op.f("ix_comments_discussion_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(op.f("ix_discussions_repository_id"), table_name="discussions")
    op.drop_table("discussions")
    op.drop_index(op.f("ix_decisions_status"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_repository_id"), table_name="decisions")
    op.drop_table("decisions")
    op.drop_index(op.f("ix_repositories_full_name"), table_name="repositories")
    op.drop_table("repositories")
    sa.Enum(name="comment_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="discussion_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="decision_status").drop(op.get_bind(), checkfirst=True)
