"""investment thesis versions

Revision ID: 20261115_0004
Revises: 20261115_0003
Create Date: 2026-11-15 02:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261115_0004"
down_revision: str | None = "20261115_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_theses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("change_class", sa.String(length=16), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column(
            "structured_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("diff_from_previous", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("polish_agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("stream_id", "version", name="uq_thesis_stream_version"),
    )
    op.create_index("ix_investment_theses_stream_id", "investment_theses", ["stream_id"])
    op.create_index(
        "uq_thesis_one_active",
        "investment_theses",
        ["stream_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_thesis_one_pending",
        "investment_theses",
        ["stream_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING_CONFIRMATION'"),
    )


def downgrade() -> None:
    op.drop_index("uq_thesis_one_pending", table_name="investment_theses")
    op.drop_index("uq_thesis_one_active", table_name="investment_theses")
    op.drop_index("ix_investment_theses_stream_id", table_name="investment_theses")
    op.drop_table("investment_theses")