"""Corrige l'enregistrement des évaluations dans la base NASORA.

La table evaluation doit exister avant de rendre tenant_id nullable.
Cette migration dépend donc aussi de la révision qui crée la table evaluation.
Le changement conserve les données existantes.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261003_eval_tenant"
down_revision = ("20261003_prospection_relances", "7d33a2945cc2")
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "evaluation",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM evaluation WHERE tenant_id IS NULL")
    ).scalar()
    if null_count:
        raise RuntimeError(
            "Impossible de remettre evaluation.tenant_id en NOT NULL : "
            f"{null_count} ligne(s) contiennent NULL."
        )
    op.alter_column(
        "evaluation",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
