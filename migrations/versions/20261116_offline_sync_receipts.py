"""Add idempotency receipts for offline field submissions.

Revision ID: 20261116_offline_sync_receipts
Revises: c8f6a2d9e410
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_offline_sync_receipts"
down_revision = "c8f6a2d9e410"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "offline_sync_receipt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "submission_id", name="uq_offline_sync_user_submission"),
    )
    op.create_index("ix_offline_sync_receipt_user_id", "offline_sync_receipt", ["user_id"])


def downgrade():
    op.drop_index("ix_offline_sync_receipt_user_id", table_name="offline_sync_receipt")
    op.drop_table("offline_sync_receipt")
