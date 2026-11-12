"""Track uploaded sales independently from manually entered sales.

Revision ID: c91e4a7b2d60
Revises: b6c3d9e2f741
"""
from alembic import op
import sqlalchemy as sa

revision = "c91e4a7b2d60"
down_revision = "b6c3d9e2f741"
branch_labels = None
depends_on = None

SALE_TABLES = (
    "nova_pharma_sale",
    "gilbert_sale",
    "eric_favre_sale",
    "trois_chene_sale",
)


def upgrade():
    for table_name in SALE_TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "is_imported",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index(
            f"ix_{table_name}_is_imported",
            table_name,
            ["is_imported"],
        )


def downgrade():
    # Keep the provenance marker and its data on rollback.
    pass
