"""Add background jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-17 01:41:11.051181
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Enum("sync", "extract", name="job_kind"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", name="job_status"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_repository_id", "jobs", ["repository_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_repository_id", table_name="jobs")
    op.drop_table("jobs")
    sa.Enum(name="job_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="job_kind").drop(op.get_bind(), checkfirst=True)
