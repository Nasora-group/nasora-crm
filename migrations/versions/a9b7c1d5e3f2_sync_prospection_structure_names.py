"""Synchronize historical prospection structure names from CRM clients.

Revision ID: a9b7c1d5e3f2
Revises: f8c2a6d4e9b1
"""
from alembic import op

revision = "a9b7c1d5e3f2"
down_revision = "f8c2a6d4e9b1"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Highest-confidence match: the explicit CRM foreign key.
    op.execute("""
        UPDATE prospection p
        SET establishment = NULLIF(BTRIM(c.establishment), '')
        FROM crm_client c
        WHERE p.client_id = c.id
          AND NULLIF(BTRIM(p.establishment), '') IS NULL
          AND NULLIF(BTRIM(c.establishment), '') IS NOT NULL
    """)

    # 2) Historical rows that were imported before client_id was populated:
    # match by normalized phone number, but only when the phone identifies
    # exactly one CRM client having a non-empty establishment.
    op.execute("""
        UPDATE prospection p
        SET establishment = x.establishment
        FROM (
            SELECT p2.id AS prospection_id, MAX(BTRIM(c.establishment)) AS establishment
            FROM prospection p2
            JOIN crm_client c
              ON regexp_replace(COALESCE(p2.telephone, ''), '[^0-9]', '', 'g') =
                 regexp_replace(COALESCE(c.phone, ''), '[^0-9]', '', 'g')
            WHERE NULLIF(BTRIM(p2.establishment), '') IS NULL
              AND NULLIF(BTRIM(c.establishment), '') IS NOT NULL
              AND regexp_replace(COALESCE(p2.telephone, ''), '[^0-9]', '', 'g') <> ''
              AND regexp_replace(COALESCE(c.phone, ''), '[^0-9]', '', 'g') <> ''
            GROUP BY p2.id
            HAVING COUNT(DISTINCT c.id) = 1
        ) x
        WHERE p.id = x.prospection_id
          AND NULLIF(BTRIM(p.establishment), '') IS NULL
    """)

    # 3) Last-resort safe match by normalized professional name + commercial
    # owner. Only unique CRM matches are accepted, avoiding false positives.
    op.execute("""
        UPDATE prospection p
        SET establishment = x.establishment
        FROM (
            SELECT p2.id AS prospection_id, MAX(BTRIM(c.establishment)) AS establishment
            FROM prospection p2
            JOIN crm_client c
              ON lower(regexp_replace(BTRIM(p2.nom_client), '[[:space:]]+', ' ', 'g')) =
                 lower(regexp_replace(BTRIM(c.name), '[[:space:]]+', ' ', 'g'))
             AND (c.owner_id = p2.commercial_id OR c.owner_id IS NULL)
            WHERE NULLIF(BTRIM(p2.establishment), '') IS NULL
              AND NULLIF(BTRIM(c.establishment), '') IS NOT NULL
              AND NULLIF(BTRIM(p2.nom_client), '') IS NOT NULL
            GROUP BY p2.id
            HAVING COUNT(DISTINCT c.id) = 1
        ) x
        WHERE p.id = x.prospection_id
          AND NULLIF(BTRIM(p.establishment), '') IS NULL
    """)


def downgrade():
    # Data migration is intentionally non-destructive. Do not erase structure
    # names that may have been entered or corrected after this migration.
    pass
