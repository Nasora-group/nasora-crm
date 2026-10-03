"""Corrige l'enregistrement des évaluations dans la base NASORA.

La table evaluation contient déjà un tenant_id ajouté côté base,
mais le modèle Evaluation actuel ne renseigne pas ce champ.
Le rendre nullable permet de conserver la compatibilité avec le modèle
actuel et de restaurer l'enregistrement des évaluations sans modifier
les données existantes.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261003_evaluation_tenant_nullable"
down_revision = "20261003_prospection_relances"
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
    # Les lignes existantes peuvent contenir NULL après l'upgrade.
    # Le downgrade est donc volontairement bloqué plutôt que de risquer
    # une perte ou une modification silencieuse de données.
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
