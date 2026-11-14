"""Backfill existing user-to-laboratory distribution assignments.

Revision ID: c8f6a2d9e410
Revises: b7e5f1c9a420
"""
from alembic import op
import sqlalchemy as sa

revision = "c8f6a2d9e410"
down_revision = "b7e5f1c9a420"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Preserve existing access by assigning each account to all active labs
    # in its current section. Administrators remain unrestricted.
    bind.execute(sa.text("""
        INSERT INTO laboratory_staff (laboratory_id, user_id)
        SELECT l.id, u.id
        FROM laboratory l
        JOIN "user" u ON lower(u.project) = lower(l.section)
        WHERE l.is_active = TRUE
          AND u.role <> 'admin'
          AND NOT EXISTS (
              SELECT 1 FROM laboratory_staff ls
              WHERE ls.laboratory_id = l.id AND ls.user_id = u.id
          )
    """))


def downgrade():
    # Keep assignments to avoid unexpectedly revoking access on downgrade.
    pass
