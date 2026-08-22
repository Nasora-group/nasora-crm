"""Add historical visit quality flags and KPI index.

Revision ID: f3a8b7c9d1e2
Revises: e1c7f4a9b2d6
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a8b7c9d1e2"
down_revision = "e1c7f4a9b2d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "crm_client_visit",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_crm_visit_commercial_date_duplicate",
        "crm_client_visit",
        ["commercial_id", "date", "is_duplicate"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_crm_visit_commercial_date_duplicate", table_name="crm_client_visit")
    op.drop_column("crm_client_visit", "is_duplicate")
