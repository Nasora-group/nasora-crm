"""Fix planning inserts for the production tenant schema.

The production planning table contains a required tenant_id column, while the
legacy ORM model does not populate that column yet. Existing planning rows
belong to the NASORA tenant (id 116). A database-side default lets the legacy
planning create/edit flows continue to insert rows without reintroducing the
old duplicate-week restriction.
"""

from alembic import op

revision = "20260906_fix_plan_tenant"
down_revision = "20260906_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE planning ALTER COLUMN tenant_id SET DEFAULT 116")


def downgrade():
    op.execute("ALTER TABLE planning ALTER COLUMN tenant_id DROP DEFAULT")
