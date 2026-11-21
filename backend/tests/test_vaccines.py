# backend/tests/test_vaccines.py
# P3 — Tests for vaccines.py (vaccines_due)
# WHY: Missed vaccines are recorded incorrectly; wrong due-list causes confusion.
#      Schedule logic must be tested at key age boundaries per PLAN.
# Run: cd backend && pytest tests/test_vaccines.py -v

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from app.brain.vaccines import vaccines_due

# ─── Fixture schedule that mirrors vaccine_schedule.json structure ─────────────
# WHY: Tests must NOT depend on the real JSON file changing.

FIXTURE_SCHEDULE = {
    "child": [
        {"id": "BCG",    "label": "BCG",           "due_weeks": 0},
        {"id": "OPV1",   "label": "OPV 1",          "due_weeks": 6},
        {"id": "PENTA1", "label": "Pentavalent 1",  "due_weeks": 6},
        {"id": "OPV2",   "label": "OPV 2",          "due_weeks": 10},
        {"id": "PENTA2", "label": "Pentavalent 2",  "due_weeks": 10},
        {"id": "OPV3",   "label": "OPV 3",          "due_weeks": 14},
        {"id": "PENTA3", "label": "Pentavalent 3",  "due_weeks": 14},
        {"id": "MR1",    "label": "MR 1",            "due_weeks": 38},
    ],
    "mother": [
        {"id": "TD1", "label": "Td 1"},
        {"id": "TD2", "label": "Td 2", "min_gap_weeks_after": ["TD1", 4]},
    ],
}

TODAY = date(2026, 11, 21)


@pytest.fixture(autouse=True)
def mock_schedule(monkeypatch):
    import app.brain.vaccines as vac_mod
    monkeypatch.setattr(vac_mod, "_load_schedule", lambda: FIXTURE_SCHEDULE)


# ════════════════════════════════════════════════════════════════════════════════
# Child schedule — age boundary tests
# ════════════════════════════════════════════════════════════════════════════════

def dob_weeks_ago(weeks: float) -> date:
    """Return a date that is `weeks` weeks before TODAY."""
    return TODAY - timedelta(days=int(weeks * 7))


class TestChildVaccinesDue:
    def test_age_0_weeks_only_birth_doses_due(self):
        """Newborn on day 0 — only BCG (due_weeks=0) is due."""
        dob = TODAY  # born today
        result = vaccines_due("child", dob, [], TODAY)
        assert "BCG" in result
        assert "OPV1" not in result
        assert "PENTA1" not in result

    def test_age_6_weeks_all_6wk_doses_due(self):
        """At 6 weeks: BCG, OPV1, PENTA1 all due."""
        dob = dob_weeks_ago(6)
        result = vaccines_due("child", dob, [], TODAY)
        assert "BCG" in result
        assert "OPV1" in result
        assert "PENTA1" in result

    def test_age_6_weeks_bcg_already_given(self):
        """BCG given at birth — should not appear in due list at 6 weeks."""
        dob = dob_weeks_ago(6)
        result = vaccines_due("child", dob, ["BCG"], TODAY)
        assert "BCG" not in result
        assert "OPV1" in result

    def test_age_10_weeks_all_10wk_doses_due(self):
        """At 10 weeks: OPV2, PENTA2 due (plus any earlier not given)."""
        dob = dob_weeks_ago(10)
        result = vaccines_due("child", dob, ["BCG", "OPV1", "PENTA1"], TODAY)
        assert "OPV2" in result
        assert "PENTA2" in result
        assert "OPV3" not in result  # 14 weeks — not yet

    def test_age_14_weeks_14wk_doses_due(self):
        """At 14 weeks: OPV3, PENTA3 due."""
        dob = dob_weeks_ago(14)
        given = ["BCG", "OPV1", "PENTA1", "OPV2", "PENTA2"]
        result = vaccines_due("child", dob, given, TODAY)
        assert "OPV3" in result
        assert "PENTA3" in result
        assert "MR1" not in result  # 38 weeks — not yet

    def test_age_38_weeks_mr1_due(self):
        """At 9 months (~38 weeks): MR1 due."""
        dob = dob_weeks_ago(38)
        given = ["BCG", "OPV1", "PENTA1", "OPV2", "PENTA2", "OPV3", "PENTA3"]
        result = vaccines_due("child", dob, given, TODAY)
        assert "MR1" in result

    def test_all_given_nothing_due(self):
        """All vaccines already given — nothing due."""
        dob = dob_weeks_ago(40)
        all_ids = [e["id"] for e in FIXTURE_SCHEDULE["child"]]
        result = vaccines_due("child", dob, all_ids, TODAY)
        assert result == []

    def test_schedule_order_preserved(self):
        """Due vaccines come back in schedule order (BCG before OPV1 etc.)."""
        dob = dob_weeks_ago(14)
        result = vaccines_due("child", dob, [], TODAY)
        bcg_idx = result.index("BCG")
        opv1_idx = result.index("OPV1")
        penta1_idx = result.index("PENTA1")
        opv2_idx = result.index("OPV2")
        assert bcg_idx < opv1_idx < penta1_idx
        assert opv1_idx < opv2_idx

    def test_dob_none_returns_empty_not_all(self):
        """DOB unknown → return empty list. Caller must ask for DOB.
        WHY: not_mentioned ≠ absent (AGENTS rule 4). We document this in vaccines.py."""
        result = vaccines_due("child", None, [], TODAY)
        assert result == []

    def test_given_ids_none_treated_as_empty(self):
        """given_ids=None should not crash; treat as empty list."""
        dob = dob_weeks_ago(6)
        result = vaccines_due("child", dob, None, TODAY)
        assert "BCG" in result

    def test_1_day_old_only_birth_doses(self):
        """1 day old — age < 1 week, only due_weeks=0 vaccines."""
        dob = TODAY - timedelta(days=1)
        result = vaccines_due("child", dob, [], TODAY)
        assert "BCG" in result
        assert "OPV1" not in result


# ════════════════════════════════════════════════════════════════════════════════
# Mother schedule (Td1 / Td2)
# ════════════════════════════════════════════════════════════════════════════════

class TestMotherVaccinesDue:
    def test_neither_given_td1_due(self):
        """Neither TD1 nor TD2 given → TD1 is due first."""
        result = vaccines_due("mother", None, [], TODAY)
        assert "TD1" in result
        assert "TD2" not in result  # TD1 must come first

    def test_td1_given_td2_due(self):
        """TD1 given → TD2 is now due."""
        result = vaccines_due("mother", None, ["TD1"], TODAY)
        assert "TD1" not in result
        assert "TD2" in result

    def test_both_given_nothing_due(self):
        result = vaccines_due("mother", None, ["TD1", "TD2"], TODAY)
        assert result == []

    def test_td2_given_without_td1_nothing_due(self):
        """Unusual but: TD2 given, TD1 not in list.
        Our logic: TD1 not in given_set → TD1 due.
        (Real scenario: catch-up or data error. We surface it.)"""
        result = vaccines_due("mother", None, ["TD2"], TODAY)
        assert "TD1" in result


# ════════════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_unknown_kind_returns_empty(self):
        result = vaccines_due("other", None, [], TODAY)
        assert result == []

    def test_future_dob_returns_only_birth_doses(self):
        """DOB is today — age = 0 weeks — only due_weeks=0 vaccines."""
        result = vaccines_due("child", TODAY, [], TODAY)
        assert "BCG" in result
        assert "OPV1" not in result

    def test_duplicate_given_ids_handled(self):
        """given_ids with duplicates should not crash."""
        dob = dob_weeks_ago(6)
        result = vaccines_due("child", dob, ["BCG", "BCG", "OPV1"], TODAY)
        assert "BCG" not in result
        assert "OPV1" not in result
        assert "PENTA1" in result
