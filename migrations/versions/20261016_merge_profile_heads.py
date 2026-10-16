"""Merge the profile, evaluation, stock/planning, and tenant-evaluation Alembic heads.

Revision ID: 20261016_merge_profile_heads
Revises: 20261016_user_profile, 7d33a2945cc2, c8e4f1a7b2d9, 20261003_eval_tenant
Create Date: 2026-10-16

Merge-only revision. It does not alter application tables or user data.
"""
from alembic import op

revision = "20261016_merge_profile_heads"
down_revision = (
    "20261016_user_profile",
    "7d33a2945cc2",
    "c8e4f1a7b2d9",
    "20261003_eval_tenant",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
