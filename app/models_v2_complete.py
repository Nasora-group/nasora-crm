from datetime import datetime
from app.extensions import db


class V2Opportunity(db.Model):
    __tablename__ = "v2_opportunity"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("crm_client.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    division = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=True)
    stage = db.Column(db.String(50), nullable=False, default="prospect", index=True)
    interest_level = db.Column(db.String(30), nullable=True)
    potential_prescription = db.Column(db.Integer, nullable=False, default=0)
    obtained_prescription = db.Column(db.Integer, nullable=False, default=0)
    next_followup = db.Column(db.Date, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    client = db.relationship("Client")
    owner = db.relationship("User")
    __table_args__ = (db.CheckConstraint("potential_prescription >= 0", name="ck_v2_opp_potential_nonnegative"),)


class V2PlanningExecution(db.Model):
    __tablename__ = "v2_planning_execution"
    id = db.Column(db.Integer, primary_key=True)
    planning_id = db.Column(db.Integer, db.ForeignKey("planning.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    execution_date = db.Column(db.Date, nullable=False, index=True)
    weekday = db.Column(db.String(20), nullable=True)
    structure_type = db.Column(db.String(100), nullable=True)
    structure_name = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("crm_client.id", ondelete="SET NULL"), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="planned", index=True)
    reason = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    realized_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship("User")
    planning = db.relationship("Planning")
    client = db.relationship("Client")
    __table_args__ = (
        db.UniqueConstraint("user_id", "execution_date", "structure_name", name="uq_v2_execution_user_date_structure"),
    )


class V2VisitGeo(db.Model):
    __tablename__ = "v2_visit_geo"
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey("crm_client_visit.id", ondelete="CASCADE"), nullable=False, unique=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy_m = db.Column(db.Float, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    captured_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source = db.Column(db.String(30), nullable=False, default="browser")
    visit = db.relationship("ClientVisit")


class V2Rupture(db.Model):
    __tablename__ = "v2_rupture"
    id = db.Column(db.Integer, primary_key=True)
    division = db.Column(db.String(50), nullable=False, index=True)
    laboratory = db.Column(db.String(150), nullable=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    wholesaler = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    reported_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = db.Column(db.String(30), nullable=False, default="rupture", index=True)
    procurement_at = db.Column(db.DateTime, nullable=True)
    stock_available_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    reported_by = db.relationship("User")


class V2RestockRequest(db.Model):
    __tablename__ = "v2_restock_request"
    id = db.Column(db.Integer, primary_key=True)
    division = db.Column(db.String(50), nullable=False, index=True)
    laboratory = db.Column(db.String(150), nullable=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    wholesaler = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = db.Column(db.String(30), nullable=False, default="requested", index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    requested_by = db.relationship("User")


class V2Objective(db.Model):
    __tablename__ = "v2_objective"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    division = db.Column(db.String(50), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)
    metric = db.Column(db.String(40), nullable=False, index=True)
    target_value = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("user_id", "division", "year", "month", "metric", name="uq_v2_objective_scope_period_metric"),
    )
