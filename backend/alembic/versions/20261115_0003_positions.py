"""spot and perpetual positions

Revision ID: 20261115_0003
Revises: 20261115_0002
Create Date: 2026-11-15 02:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261115_0003"
down_revision: str | None = "20261115_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("avg_cost", sa.Numeric(38, 18), nullable=False),
        sa.Column("cost_currency", sa.String(length=16), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(38, 18), nullable=False),
        sa.Column("fee_paid", sa.Numeric(38, 18), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "position_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=True),
        sa.Column("price", sa.Numeric(38, 18), nullable=True),
        sa.Column("fee", sa.Numeric(38, 18), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resulting_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_position_events_stream_id", "position_events", ["stream_id"])

    op.create_table(
        "position_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column("position_version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("avg_cost", sa.Numeric(38, 18), nullable=False),
        sa.Column("cost_currency", sa.String(length=16), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(38, 18), nullable=False),
        sa.Column(
            "source_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("position_events.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_position_snapshots_stream_id", "position_snapshots", ["stream_id"])

    op.create_table(
        "derivative_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity_base", sa.Numeric(38, 18), nullable=False),
        sa.Column("entry_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("leverage", sa.Numeric(10, 4), nullable=False),
        sa.Column("margin_mode", sa.String(length=16), nullable=False),
        sa.Column("margin", sa.Numeric(38, 18), nullable=False),
        sa.Column("liquidation_price", sa.Numeric(38, 18), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(38, 18), nullable=False),
        sa.Column("funding_fees", sa.Numeric(38, 18), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("stream_id", "instrument_id", name="uq_derivative_position_stream"),
    )
    op.create_index(
        "ix_derivative_positions_stream_id", "derivative_positions", ["stream_id"]
    )

    op.create_table(
        "derivative_position_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derivative_positions.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity_base", sa.Numeric(38, 18), nullable=True),
        sa.Column("price", sa.Numeric(38, 18), nullable=True),
        sa.Column("fee", sa.Numeric(38, 18), nullable=False),
        sa.Column("margin_delta", sa.Numeric(38, 18), nullable=True),
        sa.Column("funding_amount", sa.Numeric(38, 18), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resulting_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_derivative_position_events_stream_id",
        "derivative_position_events",
        ["stream_id"],
    )
    op.create_index(
        "ix_derivative_position_events_position_id",
        "derivative_position_events",
        ["position_id"],
    )

    op.create_table(
        "derivative_position_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derivative_positions.id"),
            nullable=False,
        ),
        sa.Column("position_version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity_base", sa.Numeric(38, 18), nullable=False),
        sa.Column("entry_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("leverage", sa.Numeric(10, 4), nullable=False),
        sa.Column("margin_mode", sa.String(length=16), nullable=False),
        sa.Column("margin", sa.Numeric(38, 18), nullable=False),
        sa.Column("liquidation_price", sa.Numeric(38, 18), nullable=True),
        sa.Column("mark_price", sa.Numeric(38, 18), nullable=True),
        sa.Column("notional", sa.Numeric(38, 18), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(38, 18), nullable=True),
        sa.Column("roe", sa.Numeric(10, 4), nullable=True),
        sa.Column("liq_distance_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("risk_budget_usage_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "source_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derivative_position_events.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_derivative_position_snapshots_stream_id",
        "derivative_position_snapshots",
        ["stream_id"],
    )
    op.create_index(
        "ix_derivative_position_snapshots_position_id",
        "derivative_position_snapshots",
        ["position_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_derivative_position_snapshots_position_id",
        table_name="derivative_position_snapshots",
    )
    op.drop_index(
        "ix_derivative_position_snapshots_stream_id",
        table_name="derivative_position_snapshots",
    )
    op.drop_table("derivative_position_snapshots")
    op.drop_index(
        "ix_derivative_position_events_position_id",
        table_name="derivative_position_events",
    )
    op.drop_index(
        "ix_derivative_position_events_stream_id",
        table_name="derivative_position_events",
    )
    op.drop_table("derivative_position_events")
    op.drop_index("ix_derivative_positions_stream_id", table_name="derivative_positions")
    op.drop_table("derivative_positions")
    op.drop_index("ix_position_snapshots_stream_id", table_name="position_snapshots")
    op.drop_table("position_snapshots")
    op.drop_index("ix_position_events_stream_id", table_name="position_events")
    op.drop_table("position_events")
    op.drop_table("positions")