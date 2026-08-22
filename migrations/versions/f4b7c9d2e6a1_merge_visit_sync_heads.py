"""Merge the existing Alembic heads before the visit-unification migration.

Revision ID: f4b7c9d2e6a1
Revises: f3a8b7c9d1e2, 8b4c6d7e9f10
"""

revision = "f4b7c9d2e6a1"
down_revision = ("f3a8b7c9d1e2", "8b4c6d7e9f10")
branch_labels = None
depends_on = None


def upgrade():
    # Pure Alembic merge revision: both branches already contain their own
    # schema/data changes. No additional SQL is required here.
    pass


def downgrade():
    # Do not automatically undo either branch; both contain legitimate
    # historical migrations and data changes.
    pass
