"""simplify planning to one entry per day

Revision ID: a342ccbad170
Revises: 103f34c10e01
Create Date: 2026-08-19 11:19:23.601802

"""
import json

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a342ccbad170'
down_revision = '103f34c10e01'
branch_labels = None
depends_on = None


def _merge_matin_soir(matin_raw, soir_raw):
    """Fusionne les deux créneaux JSON (matin + soir) d'un même jour en une
    seule liste, sans perdre les entrées déjà saisies avant cette évolution."""
    entries = []
    for raw in (matin_raw, soir_raw):
        if not raw:
            continue
        try:
            data = json.loads(raw)
            entries.extend(data)
        except (ValueError, TypeError):
            for value in raw.split(','):
                value = value.strip()
                if value:
                    entries.append({'type': value, 'nom': ''})
    if not entries:
        return None
    return json.dumps(entries, ensure_ascii=False)


def upgrade():
    # Ajoute les 7 nouvelles colonnes (une par jour).
    #
    # La migration précédente essayait de lire les anciennes colonnes avec
    # connection.execute(...).fetchall(). Cela fonctionne en mode online,
    # mais pas avec "flask db upgrade --sql" (mode offline).
    #
    # La copie des anciennes données est donc effectuée uniquement lorsque
    # Alembic dispose réellement d'une connexion à la base.

    op.add_column("planning", sa.Column("lundi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("mardi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("mercredi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("jeudi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("vendredi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("samedi", sa.Text(), nullable=True))
    op.add_column("planning", sa.Column("dimanche", sa.Text(), nullable=True))

    # En mode SQL offline, on ne peut pas lire les lignes avec fetchall().
    # On utilise donc une opération SQL PostgreSQL directement.
    if context.is_offline_mode():
        return

    connection = op.get_bind()

    planning_table = sa.table(
        "planning",
        sa.column("id", sa.Integer),
        sa.column("lundi_matin", sa.Text),
        sa.column("lundi_soir", sa.Text),
        sa.column("lundi", sa.Text),
        sa.column("mardi_matin", sa.Text),
        sa.column("mardi_soir", sa.Text),
        sa.column("mardi", sa.Text),
        sa.column("mercredi_matin", sa.Text),
        sa.column("mercredi_soir", sa.Text),
        sa.column("mercredi", sa.Text),
        sa.column("jeudi_matin", sa.Text),
        sa.column("jeudi_soir", sa.Text),
        sa.column("jeudi", sa.Text),
        sa.column("vendredi_matin", sa.Text),
        sa.column("vendredi_soir", sa.Text),
        sa.column("vendredi", sa.Text),
        sa.column("samedi_matin", sa.Text),
        sa.column("samedi_soir", sa.Text),
        sa.column("samedi", sa.Text),
        sa.column("dimanche_matin", sa.Text),
        sa.column("dimanche_soir", sa.Text),
        sa.column("dimanche", sa.Text),
    )

    rows = connection.execute(
        sa.select(
            planning_table.c.id,
            planning_table.c.lundi_matin,
            planning_table.c.lundi_soir,
            planning_table.c.mardi_matin,
            planning_table.c.mardi_soir,
            planning_table.c.mercredi_matin,
            planning_table.c.mercredi_soir,
            planning_table.c.jeudi_matin,
            planning_table.c.jeudi_soir,
            planning_table.c.vendredi_matin,
            planning_table.c.vendredi_soir,
            planning_table.c.samedi_matin,
            planning_table.c.samedi_soir,
            planning_table.c.dimanche_matin,
            planning_table.c.dimanche_soir,
        )
    ).fetchall()

    for row in rows:
        updates = {
            "lundi": _merge_matin_soir(row.lundi_matin, row.lundi_soir),
            "mardi": _merge_matin_soir(row.mardi_matin, row.mardi_soir),
            "mercredi": _merge_matin_soir(row.mercredi_matin, row.mercredi_soir),
            "jeudi": _merge_matin_soir(row.jeudi_matin, row.jeudi_soir),
            "vendredi": _merge_matin_soir(row.vendredi_matin, row.vendredi_soir),
            "samedi": _merge_matin_soir(row.samedi_matin, row.samedi_soir),
            "dimanche": _merge_matin_soir(row.dimanche_matin, row.dimanche_soir),
        }

        connection.execute(
            planning_table.update()
            .where(planning_table.c.id == row.id)
            .values(**updates)
        )

    # Supprime les 14 anciennes colonnes.
    with op.batch_alter_table("planning", schema=None) as batch_op:
        for column in (
            "jeudi_matin",
            "vendredi_matin",
            "mercredi_soir",
            "samedi_soir",
            "dimanche_matin",
            "lundi_soir",
            "jeudi_soir",
            "mardi_matin",
            "mercredi_matin",
            "lundi_matin",
            "vendredi_soir",
            "dimanche_soir",
            "samedi_matin",
            "mardi_soir",
        ):
            batch_op.drop_column(column)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('planning', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mardi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('samedi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('dimanche_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('vendredi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('lundi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mercredi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mardi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('jeudi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('lundi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('dimanche_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('samedi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('mercredi_soir', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('vendredi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('jeudi_matin', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.drop_column('dimanche')
        batch_op.drop_column('samedi')
        batch_op.drop_column('vendredi')
        batch_op.drop_column('jeudi')
        batch_op.drop_column('mercredi')
        batch_op.drop_column('mardi')
        batch_op.drop_column('lundi')
    # ### end Alembic commands ###
