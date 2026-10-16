"""Merge the profile and tenant-evaluation Alembic heads.

Revision ID: 20261016_merge_profile_heads
Revises: 20261016_user_profile, 20261003_eval_tenant
Create Date: 2026-10-16

Merge-only revision. It does not alter application tables or user data.
The evaluation and stock/planning revisions are already ancestors of the
 tenant-evaluation head and must not be repeated as merge parents.
"""
from alembic import op

revision = "20261016_merge_profile_heads"
down_revision = ("20261016_user_profile", "20261003_eval_tenant")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
