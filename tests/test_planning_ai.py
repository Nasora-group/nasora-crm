from datetime import date, timedelta

import pytest

from app.models import JOURS
from app.services.planning_ai import (
    PlanningCandidate,
    cycle_from_two_weeks,
    generate_two_weeks,
    planning_entries_for_week,
)


def candidates(count=80):
    return [
        PlanningCandidate(
            structure="PHARMACIES" if i % 2 else "CLINIQUE",
            name=f"Etablissement {i}",
            last_visit=date(2026, 8, 1) - timedelta(days=i),
        )
        for i in range(count)
    ]


def test_generates_exactly_two_original_weeks_with_seven_days():
    weeks = generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=5, seed=123)
    assert len(weeks) == 2
    assert all(len(week) == len(JOURS) for week in weeks)
    assert all(len(day) == 5 for week in weeks for day in week)


def test_four_week_cycle_repeats_week_one_and_two_exactly():
    weeks = generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=5, seed=123)
    cycle = cycle_from_two_weeks(weeks)
    assert cycle[2] == cycle[0]
    assert cycle[3] == cycle[1]
    assert cycle[0] is cycle[2]
    assert cycle[1] is cycle[3]


def test_two_generated_weeks_do_not_reuse_establishment_when_pool_is_large():
    weeks = generate_two_weeks(candidates(100), date(2026, 9, 7), visits_per_day=5, seed=42)
    keys = [(c.structure, c.name) for week in weeks for day in week for c in day]
    assert len(keys) == len(set(keys))


def test_generation_is_deterministic_with_seed():
    first = generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=5, seed=99)
    second = generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=5, seed=99)
    assert first == second


def test_invalid_empty_pool_is_rejected():
    with pytest.raises(ValueError, match="Aucun établissement"):
        generate_two_weeks([], date(2026, 9, 7))


def test_invalid_capacity_is_rejected():
    with pytest.raises(ValueError, match="visits_per_day"):
        generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=0)


def test_storage_conversion_preserves_day_order_and_details():
    weeks = generate_two_weeks(candidates(), date(2026, 9, 7), visits_per_day=2, seed=7)
    entries = planning_entries_for_week(weeks[0])
    assert list(entries) == JOURS
    assert all(len(entries[jour]) == 2 for jour in JOURS)
    assert all(structure and name for jour in JOURS for structure, name in entries[jour])


def test_cycle_requires_two_complete_weeks():
    with pytest.raises(ValueError, match="Deux semaines"):
        cycle_from_two_weeks([[[PlanningCandidate("PHARMACIES", "A")]]])
