from datetime import date, timedelta

from app.services.planning_ai import PlanningCandidate, generate_two_weeks


def test_no_generated_visit_can_land_on_saturday_or_sunday():
    start = date(2026, 9, 7)
    weeks = generate_two_weeks(
        [PlanningCandidate("PHARMACIES", f"Etablissement {i}") for i in range(60)],
        start,
        visits_per_day=5,
        seed=2026,
    )
    generated_dates = [
        start + timedelta(days=week_index * 7 + day_index)
        for week_index, week in enumerate(weeks)
        for day_index, _ in enumerate(week)
    ]
    assert len(generated_dates) == 10
    assert all(day.weekday() in range(5) for day in generated_dates)
