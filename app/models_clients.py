from app.extensions import db
from sqlalchemy import event, inspect


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
    visits = db.relationship("ClientVisit", back_populates="client", cascade="all, delete-orphan", order_by="ClientVisit.date.desc()")

    def __repr__(self):
        return f"<Client {self.name}>"


class ClientVisit(db.Model):
    __tablename__ = "crm_client_visit"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("crm_client.id", ondelete="CASCADE"), nullable=False, index=True)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    prospection_id = db.Column(db.Integer, db.ForeignKey("prospection.id", ondelete="SET NULL"), nullable=True, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    products_presented = db.Column(db.Text, nullable=True)
    products_prescribed = db.Column(db.Text, nullable=True)
    report = db.Column(db.Text, nullable=True)
    next_visit = db.Column(db.Date, nullable=True, index=True)
    # Historical exact duplicates are flagged, never deleted automatically.
    is_duplicate = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    client = db.relationship("Client", back_populates="visits")
    commercial = db.relationship("User", foreign_keys=[commercial_id])
    prospection = db.relationship("Prospection", foreign_keys=[prospection_id])

    __table_args__ = (
        db.Index("ix_crm_visit_commercial_date_duplicate", "commercial_id", "date", "is_duplicate"),
    )


@event.listens_for(db.session, "before_flush")
def _track_changed_client_visits(session, flush_context, instances):
    """Collect clients whose visit rows are about to change."""
    client_ids = set()
    changed = list(session.new) + list(session.dirty) + list(session.deleted)
    for visit in changed:
        if not isinstance(visit, ClientVisit):
            continue
        if visit.client_id is not None:
            client_ids.add(visit.client_id)
        if visit in session.dirty:
            history = inspect(visit).attrs.client_id.history
            for old_id in history.deleted:
                if old_id is not None:
                    client_ids.add(old_id)
        if visit in session.deleted:
            continue
        client = session.get(Client, visit.client_id) if visit.client_id is not None else None
        if (visit.prospection_id is not None and client is not None and client.owner_id is not None and client.owner_id != visit.commercial_id):
            raise ValueError("Une visite liée à une prospection ne peut pas être attribuée à un autre commercial que le propriétaire du professionnel.")
    if client_ids:
        session.info["crm_visit_date_client_ids"] = client_ids


@event.listens_for(db.session, "after_flush_postexec")
def _refresh_client_visit_dates(session, flush_context):
    """Keep Client.last_visit/next_visit aligned with persisted CRM visits."""
    client_ids = session.info.pop("crm_visit_date_client_ids", set())
    if not client_ids:
        return

    for client_id in client_ids:
        client = session.get(Client, client_id)
        if client is None:
            continue
        latest = (
            session.query(ClientVisit)
            .filter(
                ClientVisit.client_id == client_id,
                ClientVisit.is_duplicate.is_(False),
            )
            .order_by(ClientVisit.date.desc(), ClientVisit.id.desc())
            .first()
        )
        if latest is None:
            client.last_visit = None
            client.next_visit = None
        else:
            client.last_visit = latest.date
            client.next_visit = latest.next_visit