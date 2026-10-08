"""Separate consent metadata and authenticated encrypted biometric vectors."""

import sqlalchemy as sa
from alembic import op

revision = "0003_person_consent"
down_revision = "0002_temporal_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person_consents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_person_consents_expires_at", "person_consents", ["expires_at"])
    op.create_table(
        "biometric_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("consent_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("provider", sa.String(256), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_biometric_templates_consent_id", "biometric_templates", ["consent_id"])


def downgrade() -> None:
    op.drop_index("ix_biometric_templates_consent_id", table_name="biometric_templates")
    op.drop_table("biometric_templates")
    op.drop_index("ix_person_consents_expires_at", table_name="person_consents")
    op.drop_table("person_consents")
