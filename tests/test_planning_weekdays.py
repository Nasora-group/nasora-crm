from datetime import date

from app.routes.planning import _cycle_dates, _valid_week_start
from app.services.planning_ai import PlanningCandidate, cycle_from_two_weeks, generate_two_weeks, planning_entries_for_week


def test_planning_week_start_accepts_monday():
    assert _valid_week_start(date(2026, 9, 7)) is True


def test_planning_week_start_rejects_saturday():
    assert _valid_week_start(date(2026, 9, 5)) is False


def test_planning_week_start_rejects_sunday():
    assert _valid_week_start(date(2026, 9, 6)) is False


def test_cycle_dates_are_four_mondays():
    dates = _cycle_dates(date(2026, 9, 7))

    assert dates == [
        date(2026, 9, 7),
        date(2026, 9, 14),
        date(2026, 9, 21),
        date(2026, 9, 28),
    ]
    assert all(day.weekday() == 0 for day in dates)


def test_cycle_dates_reject_non_monday():
    try:
        _cycle_dates(date(2026, 9, 6))
    except ValueError as exc:
        assert "lundi" in str(exc)
    else:
        raise AssertionError("Une date de cycle non-lundi doit être rejetée")


def test_generator_creates_only_five_working_days_per_week():
    candidates = [PlanningCandidate("PHARMACIE", f"Pharmacie {index}") for index in range(12)]
    weeks = generate_two_weeks(candidates, date(2026, 9, 7), visits_per_day=2, seed=42)

    assert len(weeks) == 2
    assert all(len(week) == 5 for week in weeks)
    assert all(len(day) == 2 for week in weeks for day in week)


def test_cycle_repeats_week_one_in_week_three_and_week_two_in_week_four():
    candidates = [PlanningCandidate("PHARMACIE", f"Pharmacie {index}") for index in range(20)]
    weeks = generate_two_weeks(candidates, date(2026, 9, 7), visits_per_day=2, seed=42)
    cycle = cycle_from_two_weeks(weeks)

    assert cycle[2] == cycle[0]
    assert cycle[3] == cycle[1]


def test_generated_storage_contains_only_monday_to_friday():
    candidates = [PlanningCandidate("PHARMACIE", f"Pharmacie {index}") for index in range(10)]
    weeks = generate_two_weeks(candidates, date(2026, 9, 7), visits_per_day=1, seed=7)

    for week in weeks:
        entries = planning_entries_for_week(week)
        assert list(entries) == ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
        assert all(entries[jour] for jour in entries)
