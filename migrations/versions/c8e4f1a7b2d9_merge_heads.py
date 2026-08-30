"""Merge production and stock migration heads.

Revision ID: c8e4f1a7b2d9
Revises: a9b7c1d5e3f2, 4f8c2d1a9b77
Create Date: 2026-08-30
"""

from alembic import op

revision = "c8e4f1a7b2d9"
down_revision = ("a9b7c1d5e3f2", "4f8c2d1a9b77")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
