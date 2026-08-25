"""merge financial and prospection migration heads

Revision ID: f8c2a6d4e9b1
Revises: c7f4e8a1b2d3, e7a4b9c2d1f0
Create Date: 2026-08-25

This is a merge-only migration. It does not alter application tables or data.
It reunifies the financial migration branch and the prospection/planning branch
so Alembic has a single head.
"""
from alembic import op

revision = "f8c2a6d4e9b1"
down_revision = ("c7f4e8a1b2d3", "e7a4b9c2d1f0")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
