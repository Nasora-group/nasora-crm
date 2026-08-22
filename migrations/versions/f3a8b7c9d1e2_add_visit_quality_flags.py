"""Add historical visit quality flags and KPI index.

Revision ID: f3a8b7c9d1e2
Revises: e1c7f4a9b2d6
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a8b7c9d1e2"
down_revision = "e1c7f4a9b2d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "crm_client_visit",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Only exact historical duplicates are flagged: same professional,
    # commercial, date and visit content. We keep the oldest row and mark
    # later identical rows. No visit is physically deleted.
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY client_id, commercial_id, date,
                                    products_presented, products_prescribed, report
                       ORDER BY id
                   ) AS rn
            FROM crm_client_visit
        )
        UPDATE crm_client_visit AS v
        SET is_duplicate = TRUE
        FROM ranked r
        WHERE v.id = r.id AND r.rn > 1
    """))

    op.create_index(
        "ix_crm_visit_commercial_date_duplicate",
        "crm_client_visit",
        ["commercial_id", "date", "is_duplicate"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_crm_visit_commercial_date_duplicate", table_name="crm_client_visit")
    op.drop_column("crm_client_visit", "is_duplicate")
