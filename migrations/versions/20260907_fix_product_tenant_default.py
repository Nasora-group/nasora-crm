"""Fix product reference creation for the production tenant schema.

The production product tables contain a required tenant_id column while the
legacy product ORM models do not populate it yet. All existing NASORA product
rows belong to tenant 116. A database-side default keeps the existing product
create/edit flows compatible with the current single-tenant application while
avoiding any data rewrite.
"""

from alembic import op

revision = "20260907_fix_product_tenant"
down_revision = "20260907_animation_sale_price"
branch_labels = None
depends_on = None


def upgrade():
    for table in (
        "gilbert_product",
        "eric_favre_product",
        "trois_chene_product",
        "nova_pharma_product",
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET DEFAULT 116")


def downgrade():
    for table in (
        "gilbert_product",
        "eric_favre_product",
        "trois_chene_product",
        "nova_pharma_product",
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id DROP DEFAULT")
