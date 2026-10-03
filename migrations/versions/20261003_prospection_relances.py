"""Ajoute le suivi des relances aux prospections.

Migration additive : aucune donnée existante n'est supprimée.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261003_prospection_relances"
down_revision = "20261001_prospection_geography"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "prospection",
        sa.Column("a_revoir", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "prospection",
        sa.Column("date_relance", sa.Date(), nullable=True),
    )
    op.add_column(
        "prospection",
        sa.Column("motif_relance", sa.Text(), nullable=True),
    )
    op.create_index("ix_prospection_a_revoir", "prospection", ["a_revoir"])
    op.create_index("ix_prospection_date_relance", "prospection", ["date_relance"])


def downgrade():
    op.drop_index("ix_prospection_date_relance", table_name="prospection")
    op.drop_index("ix_prospection_a_revoir", table_name="prospection")
    op.drop_column("prospection", "motif_relance")
    op.drop_column("prospection", "date_relance")
    op.drop_column("prospection", "a_revoir")
