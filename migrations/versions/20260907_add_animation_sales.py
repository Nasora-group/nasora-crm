"""Add dedicated animation sales history for animateurs."""

from alembic import op
import sqlalchemy as sa

revision = "20260907_animation_sales"
down_revision = "20260906_fix_plan_tenant"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "animation_sale",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("animateur_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("pharmacy_name", sa.String(length=200), nullable=False),
        sa.Column("animation_date", sa.Date(), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("project", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_animation_sale_quantity_positive"),
    )
    op.create_index("ix_animation_sale_animateur_id", "animation_sale", ["animateur_id"])
    op.create_index("ix_animation_sale_pharmacy_name", "animation_sale", ["pharmacy_name"])
    op.create_index("ix_animation_sale_animation_date", "animation_sale", ["animation_date"])
    op.create_index("ix_animation_sale_project", "animation_sale", ["project"])


def downgrade():
    op.drop_index("ix_animation_sale_project", table_name="animation_sale")
    op.drop_index("ix_animation_sale_animation_date", table_name="animation_sale")
    op.drop_index("ix_animation_sale_pharmacy_name", table_name="animation_sale")
    op.drop_index("ix_animation_sale_animateur_id", table_name="animation_sale")
    op.drop_table("animation_sale")
