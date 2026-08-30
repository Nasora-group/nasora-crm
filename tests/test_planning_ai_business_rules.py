from datetime import date

import pytest

from app.services.planning_ai import PlanningCandidate, cycle_from_two_weeks, generate_two_weeks


def test_start_must_be_monday_and_generated_days_are_weekdays():
    pool = [PlanningCandidate("PHARMACIES", str(i)) for i in range(60)]
    with pytest.raises(ValueError):
        generate_two_weeks(pool, date(2026, 9, 8))

    weeks = generate_two_weeks(pool, date(2026, 9, 7), seed=1)
    cycle = cycle_from_two_weeks(weeks)
    assert [len(w) for w in cycle] == [5, 5, 5, 5]
