"""add crm client visit

Revision ID: c4e91b72a6f0
Revises: b91f7c2a6e41
"""
from alembic import op
import sqlalchemy as sa

revision = "c4e91b72a6f0"
down_revision = "b91f7c2a6e41"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_client_visit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("crm_client.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commercial_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("products_presented", sa.Text(), nullable=True),
        sa.Column("products_prescribed", sa.Text(), nullable=True),
        sa.Column("report", sa.Text(), nullable=True),
        sa.Column("next_visit", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_crm_client_visit_client_id", "crm_client_visit", ["client_id"])
    op.create_index("ix_crm_client_visit_commercial_id", "crm_client_visit", ["commercial_id"])
    op.create_index("ix_crm_client_visit_date", "crm_client_visit", ["date"])
    op.create_index("ix_crm_client_visit_next_visit", "crm_client_visit", ["next_visit"])


def downgrade():
    op.drop_index("ix_crm_client_visit_next_visit", table_name="crm_client_visit")
    op.drop_index("ix_crm_client_visit_date", table_name="crm_client_visit")
    op.drop_index("ix_crm_client_visit_commercial_id", table_name="crm_client_visit")
    op.drop_index("ix_crm_client_visit_client_id", table_name="crm_client_visit")
    op.drop_table("crm_client_visit")
