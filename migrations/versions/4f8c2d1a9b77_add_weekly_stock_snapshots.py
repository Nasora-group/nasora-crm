"""add weekly stock snapshots

Revision ID: 4f8c2d1a9b77
Revises: 103f34c10e01
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa

revision = "4f8c2d1a9b77"
down_revision = "103f34c10e01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("wholesaler", sa.String(length=30), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("week_start", "wholesaler", "product_name", name="uq_stock_week_wholesaler_product"),
    )
    op.create_index("ix_stock_entry_week_start", "stock_entry", ["week_start"])
    op.create_index("ix_stock_entry_wholesaler", "stock_entry", ["wholesaler"])
    op.create_index("ix_stock_entry_product_name", "stock_entry", ["product_name"])


def downgrade():
    op.drop_index("ix_stock_entry_product_name", table_name="stock_entry")
    op.drop_index("ix_stock_entry_wholesaler", table_name="stock_entry")
    op.drop_index("ix_stock_entry_week_start", table_name="stock_entry")
    op.drop_table("stock_entry")
