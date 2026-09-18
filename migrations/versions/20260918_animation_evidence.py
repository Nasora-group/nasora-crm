"""Store pharmacy animation proof images in PostgreSQL.

Revision ID: 20260918_animation_evidence
Revises: 20260907_fix_crm_tenant
"""

from alembic import op
import sqlalchemy as sa


revision = "20260918_animation_evidence"
down_revision = "20260907_fix_crm_tenant"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "animation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("animateur_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("pharmacy_name", sa.String(length=200), nullable=False),
        sa.Column("animation_date", sa.Date(), nullable=False),
        sa.Column("project", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_animation_evidence_animateur_id", "animation_evidence", ["animateur_id"])
    op.create_index("ix_animation_evidence_pharmacy_name", "animation_evidence", ["pharmacy_name"])
    op.create_index("ix_animation_evidence_animation_date", "animation_evidence", ["animation_date"])
    op.create_index("ix_animation_evidence_project", "animation_evidence", ["project"])

    op.add_column(
        "animation_sale",
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("animation_evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_animation_sale_evidence_id", "animation_sale", ["evidence_id"])


def downgrade():
    op.drop_index("ix_animation_sale_evidence_id", table_name="animation_sale")
    op.drop_column("animation_sale", "evidence_id")
    op.drop_index("ix_animation_evidence_project", table_name="animation_evidence")
    op.drop_index("ix_animation_evidence_animation_date", table_name="animation_evidence")
    op.drop_index("ix_animation_evidence_pharmacy_name", table_name="animation_evidence")
    op.drop_index("ix_animation_evidence_animateur_id", table_name="animation_evidence")
    op.drop_table("animation_evidence")
