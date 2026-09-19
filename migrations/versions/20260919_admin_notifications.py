"""Create administrator activity notifications.

Revision ID: 20260919_admin_notifications
Revises: 20260919_sales_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "20260919_admin_notifications"
down_revision = "20260919_sales_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_notification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("target_url", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_notification_admin_id", "admin_notification", ["admin_id"])
    op.create_index("ix_admin_notification_actor_id", "admin_notification", ["actor_id"])
    op.create_index("ix_admin_notification_event_type", "admin_notification", ["event_type"])
    op.create_index("ix_admin_notification_is_read", "admin_notification", ["is_read"])
    op.create_index("ix_admin_notification_created_at", "admin_notification", ["created_at"])


def downgrade():
    op.drop_index("ix_admin_notification_created_at", table_name="admin_notification")
    op.drop_index("ix_admin_notification_is_read", table_name="admin_notification")
    op.drop_index("ix_admin_notification_event_type", table_name="admin_notification")
    op.drop_index("ix_admin_notification_actor_id", table_name="admin_notification")
    op.drop_index("ix_admin_notification_admin_id", table_name="admin_notification")
    op.drop_table("admin_notification")
