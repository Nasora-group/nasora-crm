"""add division to CRM clients

Revision ID: 20260919_client_division
Revises: 20260919_admin_notifications
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260919_client_division"
down_revision = "20260919_admin_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crm_client", sa.Column("division", sa.String(length=50), nullable=True))
    op.create_index("ix_crm_client_division", "crm_client", ["division"], unique=False)

    # Backfill only from an existing owner. Unassigned records remain NULL
    # so the application never guesses a division from incomplete historical data.
    op.execute(
        """
        UPDATE crm_client AS client
        SET division = LOWER(u.project)
        FROM "user" AS u
        WHERE client.owner_id = u.id
          AND LOWER(u.project) IN ('nasmedic', 'nasderm')
        """
    )


def downgrade():
    op.drop_index("ix_crm_client_division", table_name="crm_client")
    op.drop_column("crm_client", "division")
