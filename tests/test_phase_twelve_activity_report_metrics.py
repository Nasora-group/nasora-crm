"""Regression tests for activity-report planning metrics."""

from datetime import date
from types import SimpleNamespace

from app.routes.activity_reporting import (
    _execution_rate,
    _planned_entry_count,
    _prospection_counts,
)


def test_planned_entry_count_splits_comma_separated_establishments():
    raw = '[{"type":"PHARMACIES","nom":"Pharmacie A, Pharmacie B"},{"type":"CLINIQUE","nom":"Clinique C"}]'
    assert _planned_entry_count(raw) == 3


def test_planned_entry_count_keeps_unnamed_legacy_slots():
    assert _planned_entry_count('HOPITAL, CLINIQUE') == 2
    assert _planned_entry_count('[{"type":"HOPITAL","nom":""}]') == 1


def test_prospection_counts_separate_planned_and_outside_planning():
    day = date(2026, 10, 15)
    rows = [
        SimpleNamespace(commercial_id=7, date=day, planning_id=10),
        SimpleNamespace(commercial_id=7, date=day, planning_id=10),
        SimpleNamespace(commercial_id=7, date=day, planning_id=None),
    ]

    counts = _prospection_counts(rows)

    assert counts["all_by_user"][7] == 3
    assert counts["all_by_day"][day] == 3
    assert counts["linked_by_user"][7] == 2
    assert counts["linked_by_day"][day] == 2
    assert counts["outside_by_user"][7] == 1
    assert counts["outside_by_day"][day] == 1


def test_execution_rate_uses_only_linked_prospections():
    assert _execution_rate(4, 2) == 50.0
    assert _execution_rate(4, 5) == 125.0
    assert _execution_rate(0, 3) is None
