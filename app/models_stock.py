from datetime import datetime

from app.extensions import db


class StockEntry(db.Model):
    """Snapshot hebdomadaire d'un stock, classé par division et laboratoire."""

    __tablename__ = "stock_entry"

    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    division = db.Column(db.String(50), nullable=False, index=True)
    laboratory = db.Column(db.String(150), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    wholesaler = db.Column(db.String(30), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "week_start", "division", "laboratory", "wholesaler", "product_name",
            name="uq_stock_week_division_lab_wholesaler_product",
        ),
    )
