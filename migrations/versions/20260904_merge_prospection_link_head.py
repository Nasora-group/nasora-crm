"""Merge the prospection/visit linkage migration with the production head.

Revision ID: 20260904_merge_prosp_visit
Revises: d1e5f7a9c3b2, 20260901_prospection_visit_link

This merge-only revision reunifies the production head with the prospection
visit linkage migration. No application table or data is changed by this
revision itself.
"""

revision = "20260904_merge_prosp_visit"
down_revision = ("d1e5f7a9c3b2", "20260901_prospection_visit_link")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
