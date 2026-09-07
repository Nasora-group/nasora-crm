"""Add unit price to animation sales and backfill existing rows."""

from alembic import op
import sqlalchemy as sa

revision = "20260907_animation_sale_price"
down_revision = "20260907_animation_sales"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("animation_sale", sa.Column("unit_price", sa.Numeric(12, 2), nullable=True))

    # Preserve a useful amount for sales already entered by matching the
    # product name against the active product catalogs. If a product no longer
    # exists, keep 0.00 rather than failing the migration.
    op.execute(sa.text("""
        UPDATE animation_sale AS a
        SET unit_price = COALESCE(
            (SELECT p.default_price FROM nova_pharma_product p WHERE p.name = a.product_name LIMIT 1),
            (SELECT p.default_price FROM gilbert_product p WHERE p.name = a.product_name LIMIT 1),
            (SELECT p.default_price FROM eric_favre_product p WHERE p.name = a.product_name LIMIT 1),
            (SELECT p.default_price FROM trois_chene_product p WHERE p.name = a.product_name LIMIT 1),
            0.00
        )
        WHERE a.unit_price IS NULL
    """))

    op.alter_column("animation_sale", "unit_price", nullable=False, server_default="0.00")


def downgrade():
    op.drop_column("animation_sale", "unit_price")
