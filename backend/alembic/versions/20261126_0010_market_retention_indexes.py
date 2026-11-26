"""market data retention indexes

Revision ID: 20261126_0010
Revises: 20261115_0009
Create Date: 2026-11-26 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261126_0010"
down_revision: str | None = "20261115_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_market_candles_timeframe_open_time",
        "market_candles",
        ["timeframe", "open_time"],
    )
    op.create_index(
        "ix_market_snapshots_created_at",
        "market_snapshots",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_created_at", table_name="market_snapshots")
    op.drop_index("ix_market_candles_timeframe_open_time", table_name="market_candles")
