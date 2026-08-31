"""Intelligent planning generator for the four-week commercial cycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import random
from typing import Iterable


@dataclass(frozen=True)
class PlanningCandidate:
    """A real establishment previously recorded by the commercial."""

    structure: str
    name: str
    last_visit: date | None = None


def _candidate_key(candidate: PlanningCandidate) -> tuple[str, str]:
    return candidate.structure.strip().upper(), candidate.name.strip().casefold()


def _score(candidate: PlanningCandidate, reference_date: date, rng: random.Random) -> float:
    """Prioritise older visits while retaining controlled randomness."""
    if candidate.last_visit is None:
        days_since_visit = 3650
    else:
        days_since_visit = max(0, (reference_date - candidate.last_visit).days)
    return min(days_since_visit, 3650) + rng.random() * 30


def _working_dates(start_date: date, weeks: int = 2) -> list[list[date]]:
    """Return Monday-Friday dates only for each generated week."""
    if start_date.weekday() != 0:
        raise ValueError("La date de début doit être un lundi")
    return [
        [start_date + timedelta(days=week * 7 + day) for day in range(5)]
        for week in range(weeks)
    ]


def generate_two_weeks(
    candidates: Iterable[PlanningCandidate],
    start_date: date,
    visits_per_day: int = 5,
    seed: int | None = None,
) -> list[list[list[PlanningCandidate]]]:
    """Generate two original weeks, Monday-Friday only.

    Week 3 and week 4 are produced separately by ``cycle_from_two_weeks``.
    Saturday and Sunday can never receive generated establishments.
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

    for week_dates in _working_dates(start_date):
        week: list[list[PlanningCandidate]] = []
        for current_date in week_dates:
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
    """Return S1, S2, S1, S2 with five working days per week."""
    if len(weeks) != 2 or any(len(week) != 5 for week in weeks):
        raise ValueError("Deux semaines complètes de cinq jours sont nécessaires")
    return [weeks[0], weeks[1], weeks[0], weeks[1]]


def planning_entries_for_week(
    week: list[list[PlanningCandidate]],
) -> dict[str, list[tuple[str, str]]]:
    """Convert a generated Monday-Friday week to storage format."""
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi")
    if len(week) != 5:
        raise ValueError("Une semaine de planning doit contenir cinq jours ouvrés")
    return {
        jour: [(candidate.structure, candidate.name) for candidate in week[index]]
        for index, jour in enumerate(jours)
    }
