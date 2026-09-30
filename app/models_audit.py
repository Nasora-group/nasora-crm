from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(120), nullable=True, index=True)
    entity_id = db.Column(db.String(120), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
