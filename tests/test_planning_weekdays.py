from datetime import date

from app.routes.planning import _valid_week_start


def test_planning_week_start_accepts_monday():
    assert _valid_week_start(date(2026, 9, 7)) is True


def test_planning_week_start_rejects_saturday():
    assert _valid_week_start(date(2026, 9, 5)) is False


def test_planning_week_start_rejects_sunday():
    assert _valid_week_start(date(2026, 9, 6)) is False
