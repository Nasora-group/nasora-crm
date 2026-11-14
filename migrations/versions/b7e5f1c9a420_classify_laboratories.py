"""Classify laboratories and link existing supplier workspaces.

Revision ID: b7e5f1c9a420
Revises: a9d4c7e2b610
"""
from alembic import op
import sqlalchemy as sa

revision = "b7e5f1c9a420"
down_revision = "a9d4c7e2b610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("laboratory", sa.Column("section", sa.String(length=20), nullable=False, server_default="nasmedic"))
    op.add_column("laboratory", sa.Column("legacy_supplier_slug", sa.String(length=80), nullable=True))
    op.create_index("ix_laboratory_section", "laboratory", ["section"])
    op.create_index("ix_laboratory_legacy_supplier_slug", "laboratory", ["legacy_supplier_slug"], unique=True)
    bind = op.get_bind()
    rows = [
        ("Eric Favre", "eric-favre", "nasmedic", "eric_favre"),
        ("3 Chênes Pharma", "trois-chenes-pharma", "nasmedic", "trois_chene"),
        ("Gilbert", "gilbert", "nasderm", "gilbert"),
    ]
    for name, slug, section, legacy_slug in rows:
        existing = bind.execute(sa.text("SELECT id FROM laboratory WHERE legacy_supplier_slug = :legacy OR slug = :slug"), {"legacy": legacy_slug, "slug": slug}).first()
        if existing:
            bind.execute(sa.text("UPDATE laboratory SET section = :section, legacy_supplier_slug = :legacy WHERE id = :id"), {"section": section, "legacy": legacy_slug, "id": existing.id})
        else:
            bind.execute(sa.text("INSERT INTO laboratory (name, slug, section, legacy_supplier_slug, currency, is_active, created_at, updated_at) VALUES (:name, :slug, :section, :legacy, :currency, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"name": name, "slug": slug, "section": section, "legacy": legacy_slug, "currency": "EUR"})

    op.create_table(
        "laboratory_sale",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("laboratory_id", sa.Integer(), sa.ForeignKey("laboratory.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("laboratory_product.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("commercial_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("project", sa.String(20), nullable=False),
        sa.Column("is_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_laboratory_sale_quantity_positive"),
    )
    for column in ("laboratory_id", "product_id", "commercial_id", "date", "project", "is_imported"):
        op.create_index("ix_laboratory_sale_" + column, "laboratory_sale", [column])

    for legacy_slug, table_name in (("eric_favre", "eric_favre_product"), ("trois_chene", "trois_chene_product"), ("gilbert", "gilbert_product")):
        bind.execute(sa.text(f"""
            INSERT INTO laboratory_product (laboratory_id, reference, name, price_ht, is_active, created_at, updated_at)
            SELECT l.id, p.reference, p.name, p.default_price, p.is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM laboratory l CROSS JOIN {table_name} p
            WHERE l.legacy_supplier_slug = :legacy
              AND NOT EXISTS (
                  SELECT 1 FROM laboratory_product lp
                  WHERE lp.laboratory_id = l.id
                    AND ((p.reference IS NOT NULL AND lp.reference = p.reference) OR lower(lp.name) = lower(p.name))
              )
        """), {"legacy": legacy_slug})


def downgrade():
    for column in ("is_imported", "project", "date", "commercial_id", "product_id", "laboratory_id"):
        op.drop_index("ix_laboratory_sale_" + column, table_name="laboratory_sale")
    op.drop_table("laboratory_sale")
    op.drop_index("ix_laboratory_legacy_supplier_slug", table_name="laboratory")
    op.drop_index("ix_laboratory_section", table_name="laboratory")
    op.drop_column("laboratory", "legacy_supplier_slug")
    op.drop_column("laboratory", "section")
