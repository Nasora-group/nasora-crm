from datetime import datetime

from app.extensions import db


class StockEntry(db.Model):
    """Snapshot hebdomadaire d'un stock chez un grossiste.

    Cette table est indépendante des ventes et des fiches produits historiques.
    """

    __tablename__ = "stock_entry"

    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    wholesaler = db.Column(db.String(30), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "week_start",
            "wholesaler",
            "product_name",
            name="uq_stock_week_wholesaler_product",
        ),
    )
