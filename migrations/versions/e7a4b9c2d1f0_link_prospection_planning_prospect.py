"""link prospections to planning and CRM prospects

Revision ID: e7a4b9c2d1f0
Revises: b91f7c2a6e41
"""
from alembic import op
import sqlalchemy as sa

revision = "e7a4b9c2d1f0"
down_revision = "b91f7c2a6e41"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("prospection") as batch:
        batch.add_column(sa.Column("establishment", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("client_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("planning_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("planning_day", sa.String(length=20), nullable=True))
        batch.create_index("ix_prospection_establishment", ["establishment"])
        batch.create_index("ix_prospection_client_id", ["client_id"])
        batch.create_index("ix_prospection_planning_id", ["planning_id"])
        batch.create_foreign_key("fk_prospection_client", "crm_client", ["client_id"], ["id"])
        batch.create_foreign_key("fk_prospection_planning", "planning", ["planning_id"], ["id"])

def downgrade():
    with op.batch_alter_table("prospection") as batch:
        batch.drop_constraint("fk_prospection_planning", type_="foreignkey")
        batch.drop_constraint("fk_prospection_client", type_="foreignkey")
        batch.drop_index("ix_prospection_planning_id")
        batch.drop_index("ix_prospection_client_id")
        batch.drop_index("ix_prospection_establishment")
        batch.drop_column("planning_day")
        batch.drop_column("planning_id")
        batch.drop_column("client_id")
        batch.drop_column("establishment")
