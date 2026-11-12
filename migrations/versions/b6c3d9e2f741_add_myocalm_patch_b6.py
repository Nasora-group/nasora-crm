"""Add MYOCALM PATCH B/6 to the Trois Chenes catalog.

Revision ID: b6c3d9e2f741
Revises: 20261111_sales_tenant_defaults
"""

from alembic import op
import sqlalchemy as sa

revision = "b6c3d9e2f741"
down_revision = "20261111_sales_tenant_defaults"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO trois_chene_product
                (name, reference, default_price, is_active,
                 stock_duopharm, stock_ubipharm, stock_laborex, stock_sodipharm)
            SELECT
                'MYOCALM PATCH B/6', NULL, 5.60, TRUE, 0, 0, 0, 0
            WHERE NOT EXISTS (
                SELECT 1
                FROM trois_chene_product
                WHERE UPPER(TRIM(name)) = 'MYOCALM PATCH B/6'
            )
            """
        )
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO trois_chene_product
                (name, reference, default_price, is_active,
                 stock_duopharm, stock_ubipharm, stock_laborex, stock_sodipharm)
            SELECT
                'MY CARE GEL FRAICH 100ML', NULL, 4.40, TRUE, 0, 0, 0, 0
            WHERE NOT EXISTS (
                SELECT 1
                FROM trois_chene_product
                WHERE UPPER(TRIM(name)) = 'MY CARE GEL FRAICH 100ML'
            )
            """
        )
    )


def downgrade():
    # Preserve catalog rows to avoid deleting products that may have existed
    # before this migration or may be referenced by later sales.
    pass
