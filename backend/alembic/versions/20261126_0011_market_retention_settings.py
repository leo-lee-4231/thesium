"""market retention settings

Revision ID: 20261126_0011
Revises: 20261126_0010
Create Date: 2026-11-26 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261126_0011"
down_revision: str | None = "20261126_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_retention_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("candle_1h_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("candle_4h_days", sa.Integer(), nullable=False, server_default="730"),
        sa.Column("candle_1d_days", sa.Integer(), nullable=False, server_default="1825"),
        sa.Column("snapshot_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("market_retention_settings")
