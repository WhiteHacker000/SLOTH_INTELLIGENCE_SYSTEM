"""Save code locations

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-17 01:58:44.099046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discussion_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discussion_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["discussion_id"], ["discussions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discussion_id", "path", name="uq_discussion_file"),
    )
    op.create_index(
        ("ix_discussion_files_discussion_id"),
        "discussion_files",
        ["discussion_id"],
        unique=False,
    )
    op.create_index(
        ("ix_discussion_files_path"), "discussion_files", ["path"], unique=False
    )
    op.add_column("comments", sa.Column("path", sa.String(length=1024), nullable=True))
    op.add_column("comments", sa.Column("line", sa.Integer(), nullable=True))
    op.add_column(
        "comments", sa.Column("commit_sha", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("comments", "commit_sha")
    op.drop_column("comments", "line")
    op.drop_column("comments", "path")
    op.drop_index(("ix_discussion_files_path"), table_name="discussion_files")
    op.drop_index(("ix_discussion_files_discussion_id"), table_name="discussion_files")
    op.drop_table("discussion_files")
