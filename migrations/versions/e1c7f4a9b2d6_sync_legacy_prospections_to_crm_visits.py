"""Synchronize legacy prospections with CRM clients and visits.

Revision ID: e1c7f4a9b2d6
Revises: d5f8a3b1c2e4
"""
from alembic import op

revision = "e1c7f4a9b2d6"
down_revision = "d5f8a3b1c2e4"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure every legacy prospection has a CRM professional.
    op.execute("""
        INSERT INTO crm_client
            (name, specialty, structure, phone, owner_id, last_visit,
             potential, created_at, updated_at)
        SELECT p.nom_client,
               p.specialite,
               p.structure,
               NULLIF(p.telephone, ''),
               p.commercial_id,
               p.date,
               3,
               CURRENT_TIMESTAMP,
               CURRENT_TIMESTAMP
        FROM prospection p
        WHERE NOT EXISTS (
            SELECT 1
            FROM crm_client c
            WHERE (
                NULLIF(regexp_replace(COALESCE(c.phone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                AND NULLIF(regexp_replace(COALESCE(p.telephone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                AND regexp_replace(c.phone, '[^0-9]', '', 'g') = regexp_replace(p.telephone, '[^0-9]', '', 'g')
            )
            OR lower(trim(c.name)) = lower(trim(p.nom_client))
        )
    """)

    # Rebuild the CRM visit history from legacy prospections without creating
    # duplicate visits when this migration is run against an already populated CRM.
    op.execute("""
        INSERT INTO crm_client_visit
            (client_id, commercial_id, date, products_presented,
             products_prescribed, report, created_at)
        SELECT c.id,
               p.commercial_id,
               p.date,
               NULLIF(p.produits_presentes, ''),
               NULLIF(p.produits_prescrits, ''),
               NULLIF(p.profils_prospect, ''),
               CURRENT_TIMESTAMP
        FROM prospection p
        JOIN crm_client c
          ON (
              NULLIF(regexp_replace(COALESCE(c.phone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
              AND NULLIF(regexp_replace(COALESCE(p.telephone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
              AND regexp_replace(c.phone, '[^0-9]', '', 'g') = regexp_replace(p.telephone, '[^0-9]', '', 'g')
          )
          OR lower(trim(c.name)) = lower(trim(p.nom_client))
        WHERE NOT EXISTS (
            SELECT 1
            FROM crm_client_visit v
            WHERE v.client_id = c.id
              AND v.commercial_id = p.commercial_id
              AND v.date = p.date
              AND COALESCE(v.products_presented, '') = COALESCE(p.produits_presentes, '')
              AND COALESCE(v.products_prescribed, '') = COALESCE(p.produits_prescrits, '')
              AND COALESCE(v.report, '') = COALESCE(p.profils_prospect, '')
        )
    """)

    # Keep the professional's last visit aligned with the latest prospection.
    op.execute("""
        UPDATE crm_client c
        SET last_visit = x.last_visit,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT c2.id AS client_id, MAX(p.date) AS last_visit
            FROM crm_client c2
            JOIN prospection p
              ON (
                  NULLIF(regexp_replace(COALESCE(c2.phone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                  AND NULLIF(regexp_replace(COALESCE(p.telephone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                  AND regexp_replace(c2.phone, '[^0-9]', '', 'g') = regexp_replace(p.telephone, '[^0-9]', '', 'g')
              )
              OR lower(trim(c2.name)) = lower(trim(p.nom_client))
            GROUP BY c2.id
        ) x
        WHERE c.id = x.client_id
          AND (c.last_visit IS NULL OR x.last_visit > c.last_visit)
    """)


def downgrade():
    # Data-preservation migration: do not delete CRM records on downgrade.
    pass
