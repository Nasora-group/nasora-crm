"""Import legacy prospections into the CRM client base.

Revision ID: d5f8a3b1c2e4
Revises: c4e91b72a6f0
"""
from alembic import op

revision = "d5f8a3b1c2e4"
down_revision = "c4e91b72a6f0"
branch_labels = None
depends_on = None


def upgrade():
    # Create a CRM profile for legacy prospects that are not represented yet.
    # The most recent visit determines the responsible commercial and last_visit.
    op.execute("""
        INSERT INTO crm_client
            (name, specialty, structure, phone, owner_id, last_visit,
             potential, created_at, updated_at)
        SELECT p.nom_client,
               MAX(p.specialite) AS specialty,
               MAX(p.structure) AS structure,
               NULLIF(MAX(NULLIF(p.telephone, '')), '') AS phone,
               (ARRAY_AGG(p.commercial_id ORDER BY p.date DESC, p.id DESC))[1] AS owner_id,
               MAX(p.date) AS last_visit,
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
        GROUP BY lower(trim(p.nom_client)), p.nom_client
    """)


def downgrade():
    # Deliberately empty: this is a data-preservation migration. Removing rows
    # here could delete CRM clients that were subsequently enriched manually.
    pass
