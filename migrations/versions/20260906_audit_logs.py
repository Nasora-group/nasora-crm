"""Compatibility marker for the production Alembic revision.

Revision ID: 20260906_audit_logs
Revises: 20260904_merge_prosp_visit

The SaaS audit trail is application-log based and deliberately does not use a
new database table. Production was previously stamped with this revision, so
this no-op migration restores the revision to the repository without changing
any production schema or data.
"""

revision = "20260906_audit_logs"
down_revision = "20260904_merge_prosp_visit"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
