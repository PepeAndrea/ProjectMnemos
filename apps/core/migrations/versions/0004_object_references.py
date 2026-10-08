"""Encrypted local object crops with durable retention/deletion metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0004_object_references"
down_revision = "0003_person_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "object_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_object_references_entity_id", "object_references", ["entity_id"])
    op.create_index("ix_object_references_expires_at", "object_references", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_object_references_expires_at", table_name="object_references")
    op.drop_index("ix_object_references_entity_id", table_name="object_references")
    op.drop_table("object_references")
