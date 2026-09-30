def test_activity_export_applies_division_filter(monkeypatch):
    from datetime import date
    from app.routes import v2_reports

    class Query:
        def __init__(self, label):
            self.label = label
            self.filters = []
        def filter(self, *args, **kwargs):
            self.filters.extend(args)
            return self
        def join(self, *args, **kwargs):
            return self
        def all(self):
            return []

    class UserModel:
        project = object()
        id = object()

    class ProspectionModel:
        date = object()
        commercial_id = object()

    class VisitModel:
        date = object()
        commercial_id = object()
        is_duplicate = type("X", (), {"is_": lambda self, value: value})()

    captured = {}
    monkeypatch.setattr(v2_reports, "Prospection", ProspectionModel)
    monkeypatch.setattr(v2_reports, "ClientVisit", VisitModel)
    monkeypatch.setattr(v2_reports, "User", UserModel)
    monkeypatch.setattr(v2_reports, "_date_range", lambda: (date(2026, 9, 1), date(2026, 9, 30)))
    monkeypatch.setattr(v2_reports.request, "args", {"division": "nasderm"})
    monkeypatch.setattr(v2_reports, "_csv_response", lambda *args: captured.update(args=args) or "ok")
    monkeypatch.setattr(v2_reports.Prospection, "query", Query("prospection"))
    monkeypatch.setattr(v2_reports.ClientVisit, "query", Query("visit"))
    monkeypatch.setattr(v2_reports, "DIVISION_SUPPLIERS", {"nasderm": ["gilbert"], "nasmedic": ["eric_favre"]})

    with v2_reports.reports_bp.test_request_context("/v2/rapports/export/activite.csv?division=nasderm"):
        assert v2_reports.export_activity() == "ok"
        assert any(filter_expr is UserModel.project == "nasderm" for filter_expr in [])
