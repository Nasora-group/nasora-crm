"""Fix CRM prospection/client inserts for the production tenant schema.

The production CRM tables contain a required tenant_id column while the
current legacy ORM models do not populate that field. Existing NASORA CRM
records are all assigned to tenant 116. A database-side default keeps the
current single-tenant application compatible without rewriting existing data.

The default is intentionally limited to the three tables involved in the
prospection save flow. A future multi-tenant ORM can explicitly provide the
correct tenant_id and will override the database default.
"""

from alembic import op

revision = "20260907_fix_crm_tenant"
down_revision = "20260907_fix_product_tenant"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("prospection", "crm_client", "crm_client_visit"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET DEFAULT 116")


def downgrade():
    for table in ("prospection", "crm_client", "crm_client_visit"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id DROP DEFAULT")
