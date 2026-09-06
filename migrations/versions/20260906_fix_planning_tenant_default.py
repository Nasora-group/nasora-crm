"""Fix planning inserts for the production tenant schema.

The production planning table contains a required tenant_id column, while the
legacy ORM model does not populate that column yet. Existing planning rows
belong to the NASORA tenant (id 116). A database-side default lets the legacy
planning create/edit flows continue to insert rows without reintroducing the
old duplicate-week restriction.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260906_fix_planning_tenant_default"
down_revision = "20260906_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "planning",
        "tenant_id",
        server_default=sa.text("116"),
    )


def downgrade():
    op.alter_column(
        "planning",
        "tenant_id",
        server_default=None,
    )
