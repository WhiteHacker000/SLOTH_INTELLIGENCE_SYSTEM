"""Add repository sync status

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01 02:21:44.457367
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

sync_status = sa.Enum(
    "never_synced", "running", "paused", "failed", "synced", name="sync_status"
)


def upgrade() -> None:
    sync_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "repositories",
        sa.Column(
            "sync_status", sync_status, server_default="never_synced", nullable=False
        ),
    )
    # Repositories synced before this migration already have a checkpoint.
    op.execute(
        "UPDATE repositories SET sync_status = 'synced' "
        "WHERE last_synced_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("repositories", "sync_status")
    sync_status.drop(op.get_bind(), checkfirst=True)
