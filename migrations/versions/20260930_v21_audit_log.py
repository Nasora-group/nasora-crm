"""V2.1 persistent audit log.

Creates the audit_log table when it is missing. Production already contains
this table, so the migration is intentionally idempotent.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_v21_audit_log"
down_revision = "20260921_stock_tenant_default"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_log" in inspector.get_table_names():
        return
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=True),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for name, column in (
        ("ix_audit_log_tenant_id", "tenant_id"),
        ("ix_audit_log_actor_user_id", "actor_user_id"),
        ("ix_audit_log_target_user_id", "target_user_id"),
        ("ix_audit_log_action", "action"),
        ("ix_audit_log_entity_type", "entity_type"),
        ("ix_audit_log_created_at", "created_at"),
    ):
        op.create_index(name, "audit_log", [column])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_log" not in inspector.get_table_names():
        return
    for name in (
        "ix_audit_log_created_at", "ix_audit_log_entity_type",
        "ix_audit_log_action", "ix_audit_log_target_user_id",
        "ix_audit_log_actor_user_id", "ix_audit_log_tenant_id",
    ):
        op.drop_index(name, table_name="audit_log")
    op.drop_table("audit_log")
