# backend/tests/test_checks.py
# P3 — Tests for checks.py (check_weight, check_vaccine_mismatch, check_visit_type)
# WHY: These cross-checks catch data inconsistencies before saving.
#      Boundary values must be pinned exactly so thresholds can't drift.
# Run: cd backend && pytest tests/test_checks.py -v

import pytest
from app.brain.checks import check_weight, check_vaccine_mismatch, check_visit_type


# ════════════════════════════════════════════════════════════════════════════════
# check_weight
# ════════════════════════════════════════════════════════════════════════════════

class TestCheckWeight:
    # ── Plausible changes — should NOT trigger a question ──
    def test_normal_gain(self):
        """2.8 → 3.1 kg: 10.7% gain, well within ratio."""
        assert check_weight(3.1, 2.8, "child") is False

    def test_normal_loss(self):
        """3.1 → 2.9 kg: 6.5% drop, within ratio."""
        assert check_weight(2.9, 3.1, "child") is False

    def test_same_weight(self):
        assert check_weight(3.1, 3.1, "child") is False

    def test_mother_normal(self):
        assert check_weight(60.0, 58.0, "mother") is False

    # ── Suspicious changes — MUST trigger a question ──
    def test_large_drop_triggers(self):
        """3.0 → 2.0: ratio 0.667 < 0.70 → suspicious."""
        assert check_weight(2.0, 3.0, "child") is True

    def test_large_gain_triggers(self):
        """2.0 → 3.1: ratio 1.55 > 1.50 → suspicious."""
        assert check_weight(3.1, 2.0, "child") is True

    # ── Exact boundary values ──
    def test_exactly_0_70_ratio_triggers(self):
        """0.70 × last = new → at boundary → True (ask)."""
        last = 10.0
        new = 7.0  # exactly 0.70
        assert check_weight(new, last, "child") is True

    def test_just_above_0_70_no_trigger(self):
        """0.701 × last: just above boundary → False."""
        last = 10.0
        new = 7.01
        assert check_weight(new, last, "child") is False

    def test_exactly_1_50_ratio_triggers(self):
        """1.50 × last = new → at boundary → True (ask)."""
        last = 10.0
        new = 15.0  # exactly 1.50
        assert check_weight(new, last, "child") is True

    def test_just_below_1_50_no_trigger(self):
        """1.499 × last: just below boundary → False."""
        last = 10.0
        new = 14.99
        assert check_weight(new, last, "child") is False

    # ── Missing data — should NOT crash or ask ──
    def test_new_none_no_trigger(self):
        assert check_weight(None, 3.0, "child") is False

    def test_last_none_no_trigger(self):
        assert check_weight(3.0, None, "child") is False

    def test_both_none_no_trigger(self):
        assert check_weight(None, None, "child") is False

    def test_last_zero_no_trigger(self):
        """Last weight is 0 — division guard: should not raise ZeroDivisionError."""
        assert check_weight(2.8, 0, "child") is False


# ════════════════════════════════════════════════════════════════════════════════
# check_vaccine_mismatch
# ════════════════════════════════════════════════════════════════════════════════

class TestCheckVaccineMismatch:
    def test_no_mismatch(self):
        assert check_vaccine_mismatch(["PENTA1", "OPV1"], ["OPV1", "PENTA1"]) == []

    def test_extra_in_stated(self):
        """Worker says PENTA2 is due but schedule doesn't list it."""
        result = check_vaccine_mismatch(["PENTA1", "PENTA2"], ["PENTA1"])
        assert "PENTA2" in result

    def test_missing_in_stated(self):
        """Schedule says OPV1 is due but worker didn't mention it."""
        result = check_vaccine_mismatch(["PENTA1"], ["PENTA1", "OPV1"])
        assert "OPV1" in result

    def test_completely_different(self):
        result = check_vaccine_mismatch(["BCG"], ["PENTA1"])
        assert "BCG" in result
        assert "PENTA1" in result

    def test_both_empty_no_mismatch(self):
        assert check_vaccine_mismatch([], []) == []

    def test_stated_empty_expected_not(self):
        result = check_vaccine_mismatch([], ["OPV1"])
        assert "OPV1" in result

    def test_expected_empty_stated_not(self):
        result = check_vaccine_mismatch(["OPV1"], [])
        assert "OPV1" in result

    def test_none_inputs_treated_as_empty(self):
        assert check_vaccine_mismatch(None, None) == []  # type: ignore

    def test_result_is_sorted(self):
        """Output is deterministically sorted (important for test stability)."""
        result = check_vaccine_mismatch(["OPV1", "BCG"], ["PENTA1"])
        assert result == sorted(result)


# ════════════════════════════════════════════════════════════════════════════════
# check_visit_type
# ════════════════════════════════════════════════════════════════════════════════

class TestCheckVisitType:
    # ── No conflict ──
    def test_newborn_visit_for_child(self):
        assert check_visit_type("NEWBORN", "child") is False

    def test_immunisation_for_child(self):
        assert check_visit_type("IMMUNISATION", "child") is False

    def test_other_for_child(self):
        assert check_visit_type("OTHER", "child") is False

    def test_anc_for_mother(self):
        assert check_visit_type("ANC", "mother") is False

    def test_pnc_for_mother(self):
        assert check_visit_type("PNC", "mother") is False

    def test_other_for_mother(self):
        assert check_visit_type("OTHER", "mother") is False

    # ── Conflict — MUST return True ──
    def test_anc_for_child_is_conflict(self):
        """ANC visit type recorded for a child → data error."""
        assert check_visit_type("ANC", "child") is True

    def test_pnc_for_child_is_conflict(self):
        assert check_visit_type("PNC", "child") is True

    def test_newborn_for_mother_is_conflict(self):
        assert check_visit_type("NEWBORN", "mother") is True

    def test_immunisation_for_mother_is_conflict(self):
        assert check_visit_type("IMMUNISATION", "mother") is True

    # ── Case insensitivity ──
    def test_lowercase_visit_type(self):
        assert check_visit_type("anc", "mother") is False

    def test_mixed_case_visit_type(self):
        assert check_visit_type("Anc", "child") is True

    # ── Missing data — should NOT crash or flag ──
    def test_none_visit_type_no_conflict(self):
        assert check_visit_type(None, "child") is False

    def test_none_kind_no_conflict(self):
        assert check_visit_type("ANC", None) is False

    def test_both_none_no_conflict(self):
        assert check_visit_type(None, None) is False

    def test_unknown_kind_no_conflict(self):
        """Unknown kind → can't check → no false conflict raised."""
        assert check_visit_type("ANC", "other") is False
