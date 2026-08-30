from datetime import date

import pytest

from app.services.planning_ai import PlanningCandidate, generate_two_weeks


def test_tuesday_start_is_rejected():
    with pytest.raises(ValueError, match="lundi"):
        generate_two_weeks(
            [PlanningCandidate("PHARMACIES", "A")],
            date(2026, 9, 8),
        )
