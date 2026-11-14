"""agent runs and decisions

Revision ID: 20261115_0005
Revises: 20261115_0004
Create Date: 2026-11-15 03:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261115_0005"
down_revision: str | None = "20261115_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "llm_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_providers.id"),
            nullable=True,
        ),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column(
            "thesis_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_theses.id"),
            nullable=True,
        ),
        sa.Column(
            "position_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("position_snapshots.id"),
            nullable=True,
        ),
        sa.Column(
            "derivative_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derivative_position_snapshots.id"),
            nullable=True,
        ),
        sa.Column(
            "market_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_snapshots.id"),
            nullable=True,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_digest", sa.String(length=64), nullable=True),
        sa.Column("input_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("output_raw", sa.Text(), nullable=True),
        sa.Column("output_parsed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_stream_id", "agent_runs", ["stream_id"])

    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "evidence_for",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_against",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "thesis_alignment",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "position_impact",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "derivative_recommendation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "changes_since_previous",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "invalidation_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "data_quality",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "notification_recommendation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_decisions_stream_id", "decisions", ["stream_id"])


def downgrade() -> None:
    op.drop_index("ix_decisions_stream_id", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_agent_runs_stream_id", table_name="agent_runs")
    op.drop_table("agent_runs")