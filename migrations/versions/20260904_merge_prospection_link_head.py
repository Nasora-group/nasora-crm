"""Merge the prospection/visit linkage migration with the production head.

Revision ID: 20260904_merge_prospection_link_head
Revises: d1e5f7a9c3b2, 20260901_link_prospection_to_crm_visit

The prospection-to-CRM-visit linkage migration introduced a second Alembic
head. This merge-only revision reunifies it with the existing production head
so deployments can run ``flask db upgrade`` normally. No application table or
data is changed by this revision itself.
"""

revision = "20260904_merge_prospection_link_head"
down_revision = ("d1e5f7a9c3b2", "20260901_link_prospection_to_crm_visit")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
