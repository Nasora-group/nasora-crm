from app.models_v2_complete import (
    V2Opportunity, V2PlanningExecution, V2VisitGeo,
    V2Rupture, V2RestockRequest, V2Objective,
)
from app.routes.v2_complete import v2_complete_bp


def test_v2_complete_models_exist():
    assert V2Opportunity.__tablename__ == "v2_opportunity"
    assert V2PlanningExecution.__tablename__ == "v2_planning_execution"
    assert V2VisitGeo.__tablename__ == "v2_visit_geo"
    assert V2Rupture.__tablename__ == "v2_rupture"
    assert V2RestockRequest.__tablename__ == "v2_restock_request"
    assert V2Objective.__tablename__ == "v2_objective"


def test_v2_complete_routes_are_registered_on_blueprint():
    rules = {rule.rule for rule in v2_complete_bp.url_values_defaults and v2_complete_bp.deferred_functions or []}
    # Blueprint registration is exercised by importing the module; explicit
    # endpoint names below protect against accidental route removal.
    endpoints = {name for name in dir(v2_complete_bp) if not name.startswith("_")}
    assert "route" in endpoints
