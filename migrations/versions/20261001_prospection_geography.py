"""Ajoute la géographie aux prospections et aux professionnels.

Les nouvelles colonnes sont nullable pour préserver tout l'historique existant.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_prospection_geography"
down_revision = "20260921_stock_tenant_default"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prospection", sa.Column("zone", sa.String(length=100), nullable=True))
    op.add_column("prospection", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column("prospection", sa.Column("address", sa.String(length=255), nullable=True))
    op.create_index("ix_prospection_zone", "prospection", ["zone"])
    op.create_index("ix_prospection_region", "prospection", ["region"])

    op.add_column("crm_client", sa.Column("region", sa.String(length=100), nullable=True))
    op.create_index("ix_crm_client_region", "crm_client", ["region"])


def downgrade():
    op.drop_index("ix_crm_client_region", table_name="crm_client")
    op.drop_column("crm_client", "region")
    op.drop_index("ix_prospection_region", table_name="prospection")
    op.drop_index("ix_prospection_zone", table_name="prospection")
    op.drop_column("prospection", "address")
    op.drop_column("prospection", "region")
    op.drop_column("prospection", "zone")
