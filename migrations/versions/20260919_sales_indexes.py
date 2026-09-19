"""Index sale ownership columns for faster commercial/division filtering.

Revision ID: 20260919_sales_indexes
Revises: 20260918_animation_evidence
"""

from alembic import op


revision = "20260919_sales_indexes"
down_revision = "20260918_animation_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_nova_pharma_sale_commercial_id", "nova_pharma_sale", ["commercial_id"])
    op.create_index("ix_gilbert_sale_commercial_id", "gilbert_sale", ["commercial_id"])
    op.create_index("ix_eric_favre_sale_commercial_id", "eric_favre_sale", ["commercial_id"])
    op.create_index("ix_trois_chene_sale_commercial_id", "trois_chene_sale", ["commercial_id"])


def downgrade():
    op.drop_index("ix_trois_chene_sale_commercial_id", table_name="trois_chene_sale")
    op.drop_index("ix_eric_favre_sale_commercial_id", table_name="eric_favre_sale")
    op.drop_index("ix_gilbert_sale_commercial_id", table_name="gilbert_sale")
    op.drop_index("ix_nova_pharma_sale_commercial_id", table_name="nova_pharma_sale")
