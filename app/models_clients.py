from datetime import date
from app.extensions import db

class Client(db.Model):
    __tablename__ = "crm_client"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    specialty = db.Column(db.String(150), nullable=True)
    structure = db.Column(db.String(150), nullable=False, index=True)
    establishment = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    zone = db.Column(db.String(100), nullable=True, index=True)
    address = db.Column(db.String(255), nullable=True)
    potential = db.Column(db.Integer, nullable=False, default=3)
    notes = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    last_visit = db.Column(db.Date, nullable=True)
    next_visit = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())
    owner = db.relationship("User", foreign_keys=[owner_id])

    def __repr__(self):
        return f"<Client {self.name}>"
