"""market candles and snapshots

Revision ID: 20261115_0002
Revises: 20261114_0001
Create Date: 2026-11-15 01:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261115_0002"
down_revision: str | None = "20261114_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_candles",
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            primary_key=True,
        ),
        sa.Column("timeframe", sa.String(length=8), primary_key=True),
        sa.Column("open_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("open", sa.Numeric(38, 18), nullable=False),
        sa.Column("high", sa.Numeric(38, 18), nullable=False),
        sa.Column("low", sa.Numeric(38, 18), nullable=False),
        sa.Column("close", sa.Numeric(38, 18), nullable=False),
        sa.Column("volume", sa.Numeric(38, 18), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(38, 18), nullable=False),
        sa.Column("change_24h_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("volume_24h", sa.Numeric(38, 18), nullable=True),
        sa.Column("high_24h", sa.Numeric(38, 18), nullable=True),
        sa.Column("low_24h", sa.Numeric(38, 18), nullable=True),
        sa.Column("market_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("staleness", sa.String(length=16), nullable=False),
        sa.Column(
            "indicators",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "derivatives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_market_snapshots_instrument_id", "market_snapshots", ["instrument_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_instrument_id", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_table("market_candles")