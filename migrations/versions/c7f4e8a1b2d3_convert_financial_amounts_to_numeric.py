"""convert financial amounts from Float to Numeric(12,2)

Revision ID: c7f4e8a1b2d3
Revises: f4b7c9d2e6a1
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa

revision = "c7f4e8a1b2d3"
down_revision = "f4b7c9d2e6a1"
branch_labels = None
depends_on = None

PRODUCT_TABLES = (
    "nova_pharma_product",
    "gilbert_product",
    "eric_favre_product",
    "trois_chene_product",
)

SALE_TABLES = (
    "nova_pharma_sale",
    "gilbert_sale",
    "eric_favre_sale",
    "trois_chene_sale",
)


def _alter_amount(table_name, column_name, using_expression):
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.alter_column(
            column_name,
            existing_type=sa.Float(),
            type_=sa.Numeric(12, 2),
            existing_nullable=False,
            postgresql_using=using_expression,
        )


def upgrade():
    for table_name in PRODUCT_TABLES:
        _alter_amount(table_name, "default_price", "ROUND(default_price::numeric, 2)")

    for table_name in SALE_TABLES:
        _alter_amount(table_name, "price", "ROUND(price::numeric, 2)")

    _alter_amount(
        "sales_objective",
        "target_amount",
        "ROUND(target_amount::numeric, 2)",
    )


def _revert_amount(table_name, column_name):
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.alter_column(
            column_name,
            existing_type=sa.Numeric(12, 2),
            type_=sa.Float(),
            existing_nullable=False,
            postgresql_using=f"{column_name}::double precision",
        )


def downgrade():
    _revert_amount("sales_objective", "target_amount")
    for table_name in reversed(SALE_TABLES):
        _revert_amount(table_name, "price")
    for table_name in reversed(PRODUCT_TABLES):
        _revert_amount(table_name, "default_price")
