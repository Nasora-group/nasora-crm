"""add CRM client table

Revision ID: b91f7c2a6e41
Revises: 7d33a2945cc2
"""
from alembic import op
import sqlalchemy as sa

revision = "b91f7c2a6e41"
down_revision = "7d33a2945cc2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "crm_client",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("specialty", sa.String(length=150), nullable=True),
        sa.Column("structure", sa.String(length=150), nullable=False),
        sa.Column("establishment", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("zone", sa.String(length=100), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("potential", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("last_visit", sa.Date(), nullable=True),
        sa.Column("next_visit", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_client_name", "crm_client", ["name"])
    op.create_index("ix_crm_client_structure", "crm_client", ["structure"])
    op.create_index("ix_crm_client_zone", "crm_client", ["zone"])
    op.create_index("ix_crm_client_owner_id", "crm_client", ["owner_id"])

def downgrade():
    op.drop_index("ix_crm_client_owner_id", table_name="crm_client")
    op.drop_index("ix_crm_client_zone", table_name="crm_client")
    op.drop_index("ix_crm_client_structure", table_name="crm_client")
    op.drop_index("ix_crm_client_name", table_name="crm_client")
    op.drop_table("crm_client")
