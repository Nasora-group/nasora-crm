"""Add MYOCALM PATCH B/6 to the Trois Chenes catalog.

Revision ID: b6c3d9e2f741
Revises: f8c2a6d4e9b1, d1e5f7a9c3b2
"""

from alembic import op
import sqlalchemy as sa

revision = "b6c3d9e2f741"
down_revision = ("f8c2a6d4e9b1", "d1e5f7a9c3b2")
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


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM trois_chene_product AS product
            WHERE UPPER(TRIM(product.name)) = 'MYOCALM PATCH B/6'
              AND NOT EXISTS (
                  SELECT 1
                  FROM trois_chene_sale AS sale
                  WHERE sale.product_id = product.id
              )
            """
        )
    )
