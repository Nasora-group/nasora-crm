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


def downgrade():
    op.drop_index("ix_laboratory_legacy_supplier_slug", table_name="laboratory")
    op.drop_index("ix_laboratory_section", table_name="laboratory")
    op.drop_column("laboratory", "legacy_supplier_slug")
    op.drop_column("laboratory", "section")
