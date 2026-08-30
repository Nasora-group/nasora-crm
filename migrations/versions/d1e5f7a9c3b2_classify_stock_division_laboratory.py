"""Classify weekly stock snapshots by division and laboratory.

Revision ID: d1e5f7a9c3b2
Revises: c8e4f1a7b2d9
"""

from alembic import op
import sqlalchemy as sa

revision = "d1e5f7a9c3b2"
down_revision = "c8e4f1a7b2d9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_entry", sa.Column("division", sa.String(length=50), nullable=True))
    op.add_column("stock_entry", sa.Column("laboratory", sa.String(length=150), nullable=True))
    op.create_index("ix_stock_entry_division", "stock_entry", ["division"])
    op.create_index("ix_stock_entry_laboratory", "stock_entry", ["laboratory"])
    op.drop_constraint("uq_stock_week_wholesaler_product", "stock_entry", type_="unique")
    op.create_unique_constraint(
        "uq_stock_week_division_lab_wholesaler_product",
        "stock_entry",
        ["week_start", "division", "laboratory", "wholesaler", "product_name"],
    )


def downgrade():
    op.drop_constraint("uq_stock_week_division_lab_wholesaler_product", "stock_entry", type_="unique")
    op.create_unique_constraint(
        "uq_stock_week_wholesaler_product",
        "stock_entry",
        ["week_start", "wholesaler", "product_name"],
    )
    op.drop_index("ix_stock_entry_laboratory", table_name="stock_entry")
    op.drop_index("ix_stock_entry_division", table_name="stock_entry")
    op.drop_column("stock_entry", "laboratory")
    op.drop_column("stock_entry", "division")
