"""add provider key time windows

Revision ID: e2f4a6b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-03-25 11:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4a6b8c9d0"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_api_keys",
        sa.Column("time_range_start", sa.String(length=5), nullable=True),
    )
    op.add_column(
        "provider_api_keys",
        sa.Column("time_range_end", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_api_keys", "time_range_end")
    op.drop_column("provider_api_keys", "time_range_start")
