"""Add administrator-managed laboratories and independent product catalogs.

Revision ID: a9d4c7e2b610
Revises: f8c2a6d4e9b1
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "a9d4c7e2b610"
down_revision = "f8c2a6d4e9b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "laboratory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="XOF"),
        sa.Column("monthly_objective", sa.Numeric(14, 2), nullable=True),
        sa.Column("annual_objective", sa.Numeric(14, 2), nullable=True),
        sa.Column("logo_data", sa.LargeBinary(), nullable=True),
        sa.Column("logo_mime_type", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_laboratory_slug"),
    )
    op.create_index("ix_laboratory_slug", "laboratory", ["slug"], unique=True)
    op.create_table(
        "laboratory_staff",
        sa.Column("laboratory_id", sa.Integer(), sa.ForeignKey("laboratory.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "laboratory_product",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("laboratory_id", sa.Integer(), sa.ForeignKey("laboratory.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("price_ht", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("laboratory_id", "reference", name="uq_laboratory_product_reference"),
    )
    op.create_index("ix_laboratory_product_laboratory_id", "laboratory_product", ["laboratory_id"])


def downgrade():
    op.drop_index("ix_laboratory_product_laboratory_id", table_name="laboratory_product")
    op.drop_table("laboratory_product")
    op.drop_table("laboratory_staff")
    op.drop_index("ix_laboratory_slug", table_name="laboratory")
    op.drop_table("laboratory")
