from datetime import date, timedelta

from app.services.planning_ai import PlanningCandidate, generate_two_weeks


def test_generator_produces_ten_working_days_for_two_weeks():
    start = date(2026, 9, 7)
    pool = [PlanningCandidate("PHARMACIES", f"Etablissement {i}") for i in range(100)]
    weeks = generate_two_weeks(pool, start, visits_per_day=1, seed=7)
    dates = [start + timedelta(days=w * 7 + d) for w in range(2) for d in range(5)]
    assert len(weeks) == 2
    assert all(day.weekday() <= 4 for day in dates)
    assert all(len(day) == 1 for week in weeks for day in week)
