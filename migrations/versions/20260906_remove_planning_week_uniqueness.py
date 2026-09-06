"""Allow multiple planning rows for the same commercial and Monday.

Revision ID: 20260906_remove_planning_week_uniqueness
Revises: 20260906_audit_logs
"""

from alembic import op


revision = "20260906_remove_planning_week_uniqueness"
down_revision = "20260906_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    # Older production schemas may still contain a unique constraint/index on
    # (commercial_id, date), even though the SQLAlchemy model no longer does.
    # Remove only that exact two-column uniqueness so several planning rows can
    # legitimately coexist for the same commercial and week.
    op.execute(
        """
        DO $$
        DECLARE
            idx RECORD;
            constraint_name TEXT;
        BEGIN
            FOR idx IN
                SELECT
                    i.indexrelid,
                    i.relname AS index_name,
                    ARRAY(
                        SELECT a.attname
                        FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality)
                        JOIN pg_attribute a
                          ON a.attrelid = i.indrelid
                         AND a.attnum = k.attnum
                        ORDER BY a.attname
                    ) AS columns
                FROM pg_index i
                JOIN pg_class t ON t.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                  AND t.relname = 'planning'
                  AND i.indisunique
            LOOP
                IF idx.columns = ARRAY['commercial_id', 'date'] THEN
                    SELECT c.conname
                    INTO constraint_name
                    FROM pg_constraint c
                    WHERE c.conrelid = 'planning'::regclass
                      AND c.conindid = idx.indexrelid
                      AND c.contype = 'u'
                    LIMIT 1;

                    IF constraint_name IS NOT NULL THEN
                        EXECUTE format(
                            'ALTER TABLE %I DROP CONSTRAINT %I',
                            'planning',
                            constraint_name
                        );
                    ELSE
                        EXECUTE format('DROP INDEX IF EXISTS %I', idx.index_name);
                    END IF;
                END IF;
            END LOOP;
        END $$;
        """
    )


def downgrade():
    # Deliberately no-op: reintroducing a uniqueness rule would conflict with
    # planning rows that may have been legitimately created after this change.
    pass
