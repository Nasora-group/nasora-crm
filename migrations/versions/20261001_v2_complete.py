"""Complete V2.2-V2.6 domain tables."""
from alembic import op
import sqlalchemy as sa

revision = "20261001_v2_complete"
down_revision = "20260930_v21_audit_log"
branch_labels = None
depends_on = None


def _has_table(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "v2_opportunity"):
        op.create_table(
            "v2_opportunity",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("crm_client.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("division", sa.String(50), nullable=False),
            sa.Column("product_name", sa.String(200)),
            sa.Column("stage", sa.String(50), nullable=False, server_default="prospect"),
            sa.Column("interest_level", sa.String(30)),
            sa.Column("potential_prescription", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("obtained_prescription", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_followup", sa.Date()),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("potential_prescription >= 0", name="ck_v2_opp_potential_nonnegative"),
        )

    if not _has_table(inspector, "v2_planning_execution"):
        op.create_table(
            "v2_planning_execution",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("planning_id", sa.Integer(), sa.ForeignKey("planning.id", ondelete="SET NULL")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("execution_date", sa.Date(), nullable=False),
            sa.Column("weekday", sa.String(20)),
            sa.Column("structure_type", sa.String(100)),
            sa.Column("structure_name", sa.String(200), nullable=False),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("crm_client.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
            sa.Column("reason", sa.String(100)),
            sa.Column("notes", sa.Text()),
            sa.Column("realized_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "execution_date", "structure_name", name="uq_v2_execution_user_date_structure"),
        )

    if not _has_table(inspector, "v2_visit_geo"):
        op.create_table(
            "v2_visit_geo",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("crm_client_visit.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("accuracy_m", sa.Float()),
            sa.Column("duration_minutes", sa.Integer()),
            sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("source", sa.String(30), nullable=False, server_default="browser"),
        )

    if not _has_table(inspector, "v2_rupture"):
        op.create_table(
            "v2_rupture",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("division", sa.String(50), nullable=False),
            sa.Column("laboratory", sa.String(150)),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("wholesaler", sa.String(50)),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reported_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("reported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("status", sa.String(30), nullable=False, server_default="rupture"),
            sa.Column("procurement_at", sa.DateTime()),
            sa.Column("stock_available_at", sa.DateTime()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("notes", sa.Text()),
        )

    if not _has_table(inspector, "v2_restock_request"):
        op.create_table(
            "v2_restock_request",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("division", sa.String(50), nullable=False),
            sa.Column("laboratory", sa.String(150)),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("wholesaler", sa.String(50)),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
            sa.Column("processed_at", sa.DateTime()),
            sa.Column("notes", sa.Text()),
        )

    if not _has_table(inspector, "v2_objective"):
        op.create_table(
            "v2_objective",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("division", sa.String(50), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer()),
            sa.Column("metric", sa.String(40), nullable=False),
            sa.Column("target_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "division", "year", "month", "metric", name="uq_v2_objective_scope_period_metric"),
        )

    for table, cols in {
        "v2_opportunity": ["owner_id", "division", "stage", "next_followup"],
        "v2_planning_execution": ["user_id", "execution_date", "status"],
        "v2_visit_geo": ["visit_id"],
        "v2_rupture": ["division", "product_name", "status"],
        "v2_restock_request": ["division", "product_name", "status"],
        "v2_objective": ["user_id", "division", "year", "metric"],
    }.items():
        existing = {x["name"] for x in sa.inspect(bind).get_indexes(table)}
        for col in cols:
            name = f"ix_{table}_{col}"
            if name not in existing:
                op.create_index(name, table, [col])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("v2_objective", "v2_restock_request", "v2_rupture", "v2_visit_geo", "v2_planning_execution", "v2_opportunity"):
        if _has_table(inspector, table):
            op.drop_table(table)
