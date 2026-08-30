"""Intelligent planning generator.

The generator deliberately uses no external AI service: it combines historical
prospection data, zone ownership and controlled randomness. A four-week cycle
contains two generated weeks; week 3 repeats week 1 and week 4 repeats week 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import random
from typing import Iterable

from app.models import JOURS


@dataclass(frozen=True)
class PlanningCandidate:
    """A real establishment previously recorded by the commercial."""

    structure: str
    name: str
    last_visit: date | None = None


def _candidate_key(candidate: PlanningCandidate) -> tuple[str, str]:
    return candidate.structure.strip().upper(), candidate.name.strip().casefold()


def _score(candidate: PlanningCandidate, reference_date: date, rng: random.Random) -> float:
    """Prioritise older visits while retaining a small random component."""
    if candidate.last_visit is None:
        days_since_visit = 3650
    else:
        days_since_visit = max(0, (reference_date - candidate.last_visit).days)
    return min(days_since_visit, 3650) + rng.random() * 30


def generate_two_weeks(
    candidates: Iterable[PlanningCandidate],
    start_date: date,
    visits_per_day: int = 5,
    seed: int | None = None,
) -> list[list[list[PlanningCandidate]]]:
    """Generate two original weeks, seven days each.

    The same establishment is not selected twice in the generated two-week
    period when enough candidates exist. When the candidate pool is smaller
    than the requested capacity, reuse is allowed only after the pool has been
    exhausted. Returned data is independent from database objects.
    """
    if visits_per_day < 1:
        raise ValueError("visits_per_day doit être supérieur ou égal à 1")

    unique: dict[tuple[str, str], PlanningCandidate] = {}
    for candidate in candidates:
        if candidate.name.strip() and candidate.structure.strip():
            unique.setdefault(_candidate_key(candidate), candidate)

    pool = list(unique.values())
    if not pool:
        raise ValueError("Aucun établissement réel disponible pour générer le planning")

    rng = random.Random(seed)
    weeks: list[list[list[PlanningCandidate]]] = []
    used: set[tuple[str, str]] = set()

    for week_index in range(2):
        week: list[list[PlanningCandidate]] = []
        for day_index, _jour in enumerate(JOURS):
            current_date = start_date + timedelta(days=week_index * 7 + day_index)
            available = [c for c in pool if _candidate_key(c) not in used]
            if not available:
                used.clear()
                available = pool[:]

            ranked = sorted(
                available,
                key=lambda c: _score(c, current_date, rng),
                reverse=True,
            )
            selected = ranked[: min(visits_per_day, len(ranked))]
            week.append(selected)
            used.update(_candidate_key(c) for c in selected)
        weeks.append(week)

    return weeks


def cycle_from_two_weeks(
    weeks: list[list[list[PlanningCandidate]]],
) -> list[list[list[PlanningCandidate]]]:
    """Return the complete four-week cycle: S1, S2, copy(S1), copy(S2)."""
    if len(weeks) != 2 or any(len(week) != len(JOURS) for week in weeks):
        raise ValueError("Deux semaines complètes sont nécessaires")
    return [weeks[0], weeks[1], weeks[0], weeks[1]]


def planning_entries_for_week(week: list[list[PlanningCandidate]]) -> dict[str, list[tuple[str, str]]]:
    """Convert generated candidates to the existing planning storage format."""
    if len(week) != len(JOURS):
        raise ValueError("Une semaine doit contenir sept jours")
    return {
        jour: [(candidate.structure, candidate.name) for candidate in week[index]]
        for index, jour in enumerate(JOURS)
    }
