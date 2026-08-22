"""Unify Prospection and ClientVisit historical records.

Revision ID: 8b4c6d7e9f10
Revises: 7d33a2945cc2

Business rule: one real visit = one Prospection = one ClientVisit.
Existing ClientVisit rows without a matching Prospection are preserved by
creating the missing Prospection record from the CRM visit data.
"""
from alembic import op

revision = "8b4c6d7e9f10"
down_revision = "7d33a2945cc2"
branch_labels = None
depends_on = None


def upgrade():
    # Every non-duplicate CRM visit must have a corresponding Prospection.
    # Match first on the exact visit payload; fallback matching is deliberately
    # limited to the same commercial/client/date to avoid inventing unrelated
    # historical prospects.
    op.execute("""
        INSERT INTO prospection
            (commercial_id, date, nom_client, specialite, structure, telephone,
             profils_prospect, produits_presentes, produits_prescrits)
        SELECT v.commercial_id,
               v.date,
               c.name,
               COALESCE(c.specialty, 'Non renseignée'),
               c.structure,
               COALESCE(NULLIF(c.phone, ''), 'NC'),
               v.report,
               v.products_presented,
               v.products_prescribed
        FROM crm_client_visit v
        JOIN crm_client c ON c.id = v.client_id
        WHERE COALESCE(v.is_duplicate, FALSE) = FALSE
          AND NOT EXISTS (
              SELECT 1
              FROM prospection p
              WHERE p.commercial_id = v.commercial_id
                AND p.date = v.date
                AND COALESCE(p.produits_presentes, '') = COALESCE(v.products_presented, '')
                AND COALESCE(p.produits_prescrits, '') = COALESCE(v.products_prescribed, '')
                AND COALESCE(p.profils_prospect, '') = COALESCE(v.report, '')
                AND (
                    lower(trim(p.nom_client)) = lower(trim(c.name))
                    OR (
                        NULLIF(regexp_replace(COALESCE(p.telephone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                        AND NULLIF(regexp_replace(COALESCE(c.phone, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
                        AND regexp_replace(p.telephone, '[^0-9]', '', 'g') = regexp_replace(c.phone, '[^0-9]', '', 'g')
                    )
                )
          )
    """)


def downgrade():
    # Data-preservation migration: records created by this migration are not
    # deleted automatically on downgrade because they may contain legitimate
    # business history.
    pass
