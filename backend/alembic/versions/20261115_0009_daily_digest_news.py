"""daily digest and news articles

Revision ID: 20261115_0009
Revises: 20261115_0008
Create Date: 2026-11-15 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261115_0009"
down_revision: str | None = "20261115_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "daily_summary_time",
            sa.String(length=5),
            nullable=False,
            server_default=sa.text("'08:00'"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "news_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column(
            "category",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'FINANCE'"),
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False, unique=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "daily_digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "stream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investment_streams.id"),
            nullable=False,
        ),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "stream_id", "local_date", name="uq_daily_digest_stream_date"
        ),
    )
    op.create_index("ix_daily_digests_user_id", "daily_digests", ["user_id"])
    op.create_index("ix_daily_digests_stream_id", "daily_digests", ["stream_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_digests_stream_id", table_name="daily_digests")
    op.drop_index("ix_daily_digests_user_id", table_name="daily_digests")
    op.drop_table("daily_digests")
    op.drop_table("news_articles")
    op.drop_column("notification_preferences", "news_enabled")
    op.drop_column("notification_preferences", "daily_summary_time")
