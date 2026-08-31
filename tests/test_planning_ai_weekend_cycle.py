from datetime import date

from app.services.planning_ai import PlanningCandidate, cycle_from_two_weeks, generate_two_weeks


def test_complete_cycle_has_five_days_per_week_and_repeats_original_weeks():
    weeks = generate_two_weeks(
        [PlanningCandidate("PHARMACIES", f"Etablissement {i}") for i in range(60)],
        date(2026, 9, 7),
        visits_per_day=5,
        seed=17,
    )
    cycle = cycle_from_two_weeks(weeks)
    assert [len(week) for week in cycle] == [5, 5, 5, 5]
    assert cycle[2] == cycle[0]
    assert cycle[3] == cycle[1]
