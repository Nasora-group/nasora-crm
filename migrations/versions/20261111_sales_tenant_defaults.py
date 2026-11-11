"""Provide the existing NASORA tenant for supplier sales inserts.

The production sales tables have a required tenant_id column, while the
legacy supplier-sale ORM models do not yet expose that column. Existing
NASORA CRM data uses tenant 116. A database default preserves compatibility
for the current single-tenant application without rewriting existing rows.
Explicit tenant_id values supplied by a future multi-tenant model override
this default.

Revision ID: 20261111_sales_tenant_defaults
Revises: 20261016_merge_profile_heads
"""
from alembic import op

revision = "20261111_sales_tenant_defaults"
down_revision = "20261016_merge_profile_heads"
branch_labels = None
depends_on = None

SALE_TABLES = (
    "nova_pharma_sale",
    "gilbert_sale",
    "eric_favre_sale",
    "trois_chene_sale",
)


def upgrade():
    for table in SALE_TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id SET DEFAULT 116"
        )


def downgrade():
    for table in SALE_TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id DROP DEFAULT"
        )
