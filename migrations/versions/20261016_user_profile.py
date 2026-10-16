"""Add personal profile details and optional photo.

Revision ID: 20261016_user_profile
Revises: f8c2a6d4e9b1
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "20261016_user_profile"
down_revision = "f8c2a6d4e9b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("photo_data", sa.LargeBinary(), nullable=True),
        sa.Column("photo_mime_type", sa.String(length=30), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_profile_user_id", "user_profile", ["user_id"], unique=True)


def downgrade():
    op.drop_index("ix_user_profile_user_id", table_name="user_profile")
    op.drop_table("user_profile")
