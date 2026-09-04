"""Link each CRM visit to its source Prospection when available.

Revision ID: 20260901_prospection_visit_link
Revises: c8e4f1a7b2d9, 103f34c10e01

The new link is nullable so existing CRM visits remain untouched. Existing
historical rows are deliberately not backfilled or deleted.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_prospection_visit_link"
down_revision = ("c8e4f1a7b2d9", "103f34c10e01")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "crm_client_visit",
        sa.Column(
            "prospection_id",
            sa.Integer(),
            sa.ForeignKey("prospection.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_crm_client_visit_prospection_id",
        "crm_client_visit",
        ["prospection_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_crm_client_visit_prospection_id", table_name="crm_client_visit")
    op.drop_column("crm_client_visit", "prospection_id")
