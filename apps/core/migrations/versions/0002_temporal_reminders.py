"""Durable temporal reminders, local inbox and policy execution audit."""

import sqlalchemy as sa
from alembic import op

revision = "0002_temporal_reminders"
down_revision = "0001_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_reminders_due_at", "reminders", ["due_at"])
    op.create_table(
        "notifications",
        sa.Column("reminder_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "local_action_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("local_action_audit")
    op.drop_table("notifications")
    op.drop_index("ix_reminders_due_at", table_name="reminders")
    op.drop_table("reminders")
