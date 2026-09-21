"""Fix stock inserts for the production tenant schema.

The production stock_entry table requires tenant_id, while the legacy
StockEntry ORM flow does not populate it. Existing NASORA data belongs to
tenant 116, so a database-side default keeps the current stock flow working
without changing the stock route or existing data.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_fix_stock_tenant_default"
down_revision = "20260919_admin_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "stock_entry",
        "tenant_id",
        server_default=sa.text("116"),
    )


def downgrade():
    op.alter_column(
        "stock_entry",
        "tenant_id",
        server_default=None,
    )
