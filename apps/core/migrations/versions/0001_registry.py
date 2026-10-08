"""Initial entity registry and pgvector extension."""

import sqlalchemy as sa
from alembic import op

revision = "0001_registry"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("name", sa.String(4096), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_entities_kind", "entities", ["kind"])
    op.create_index("ix_entities_name", "entities", ["name"])


def downgrade() -> None:
    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_index("ix_entities_kind", table_name="entities")
    op.drop_table("entities")
