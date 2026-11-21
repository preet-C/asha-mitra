# backend/tests/test_conflicts.py
# A5 — Tests for brain/conflicts.py
#
# Covers:
#   - symptom_conflicts: present+absent in same visit
#   - value_conflicts: same field, different values, different utterances
#   - repeat_vaccines: exact ID already in history
#   - PENTA1 vs PENTA2 NOT treated as duplicates
#   - Unclear answer preserves danger flag (design contract, not tested in isolation)
#
# How to run:
#   cd backend
#   pytest tests/test_conflicts.py -v

import pytest

from app.brain.conflicts import (
    symptom_conflicts,
    value_conflicts,
    repeat_vaccines,
    run_all_conflict_checks,
)


# ─── symptom_conflicts ────────────────────────────────────────────────────────

class TestSymptomConflicts:
    def test_present_then_absent_is_conflict(self):
        """Same sign_id marked present in one entry, absent in another → conflict."""
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "NB_FEVER_OR_COLD", "status": "absent"},
        ]
        result = symptom_conflicts(log)
        assert "NB_FEVER_OR_COLD" in result

    def test_unclear_then_absent_is_conflict(self):
        """Unclear + absent for same sign → conflict (unclear is positive-ish)."""
        log = [
            {"sign_id": "MO_BLEEDING", "status": "unclear"},
            {"sign_id": "MO_BLEEDING", "status": "absent"},
        ]
        result = symptom_conflicts(log)
        assert "MO_BLEEDING" in result

    def test_present_twice_no_conflict(self):
        """Same sign present twice = no conflict."""
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
        ]
        assert symptom_conflicts(log) == []

    def test_absent_twice_no_conflict(self):
        """Same sign absent twice = no conflict."""
        log = [
            {"sign_id": "MO_BLEEDING", "status": "absent"},
            {"sign_id": "MO_BLEEDING", "status": "absent"},
        ]
        assert symptom_conflicts(log) == []

    def test_different_signs_no_conflict(self):
        """Different sign IDs: one present, one absent = no cross-conflict."""
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "MO_BLEEDING", "status": "absent"},
        ]
        assert symptom_conflicts(log) == []

    def test_empty_log_no_conflict(self):
        assert symptom_conflicts([]) == []

    def test_none_log_no_conflict(self):
        assert symptom_conflicts(None) == []

    def test_hindi_workflow_conflict(self):
        """Simulate Hindi worker saying 'bukhar hai' then 'bukhar nahi hai'."""
        # Both map to the same sign_id — the conflict detector doesn't see the words,
        # only the statuses from danger.py + LLM
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},   # bukhar hai
            {"sign_id": "NB_FEVER_OR_COLD", "status": "absent"},    # bukhar nahi hai
        ]
        result = symptom_conflicts(log)
        assert "NB_FEVER_OR_COLD" in result

    def test_multiple_conflicts_returned(self):
        """Two different signs both conflicted."""
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "NB_FEVER_OR_COLD", "status": "absent"},
            {"sign_id": "MO_BLEEDING", "status": "unclear"},
            {"sign_id": "MO_BLEEDING", "status": "absent"},
        ]
        result = symptom_conflicts(log)
        assert "NB_FEVER_OR_COLD" in result
        assert "MO_BLEEDING" in result

    def test_result_is_sorted(self):
        """Result list should be sorted for determinism."""
        log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "NB_FEVER_OR_COLD", "status": "absent"},
            {"sign_id": "MO_BLEEDING", "status": "unclear"},
            {"sign_id": "MO_BLEEDING", "status": "absent"},
        ]
        result = symptom_conflicts(log)
        assert result == sorted(result)


# ─── value_conflicts ──────────────────────────────────────────────────────────

class TestValueConflicts:
    def test_weight_different_utterances_is_conflict(self):
        """weight_kg = 2.8 in utterance 1, then 3.1 in utterance 2 → conflict."""
        log = [
            {"field": "weight_kg", "value": 2.8, "utterance": 1},
            {"field": "weight_kg", "value": 3.1, "utterance": 2},
        ]
        result = value_conflicts(log)
        fields = [c["field"] for c in result]
        assert "weight_kg" in fields

    def test_same_utterance_no_conflict(self):
        """Same utterance index = LLM already resolved → NOT a conflict."""
        log = [
            {"field": "weight_kg", "value": 2.8, "utterance": 1},
            {"field": "weight_kg", "value": 3.1, "utterance": 1},  # same utterance
        ]
        # Same utterance key → only one value per utterance taken (the last wins in dict)
        # 2.8 and 3.1 both map to utterance 1 → dict keeps only one → no conflict
        result = value_conflicts(log)
        # We should NOT see weight_kg as conflict since it's same utterance
        # (dict[utterance] = value only stores latest, so values set has 1 element)
        for c in result:
            assert c["field"] != "weight_kg"

    def test_id_different_utterances_always_conflict(self):
        """beneficiary_id changing mid-visit → always conflict."""
        log = [
            {"field": "beneficiary_id", "value": "1001", "utterance": 1},
            {"field": "beneficiary_id", "value": "1002", "utterance": 2},
        ]
        result = value_conflicts(log)
        fields = [c["field"] for c in result]
        assert "beneficiary_id" in fields

    def test_no_conflict_same_value_different_utterances(self):
        """Same value repeated in different utterances = no conflict."""
        log = [
            {"field": "weight_kg", "value": 2.8, "utterance": 1},
            {"field": "weight_kg", "value": 2.8, "utterance": 2},
        ]
        assert value_conflicts(log) == []

    def test_empty_log_no_conflict(self):
        assert value_conflicts([]) == []

    def test_none_log_no_conflict(self):
        assert value_conflicts(None) == []

    def test_conflict_contains_both_values(self):
        """Conflict dict includes both values so template can say 'I heard X and Y'."""
        log = [
            {"field": "weight_kg", "value": 2.8, "utterance": 1},
            {"field": "weight_kg", "value": 3.1, "utterance": 2},
        ]
        result = value_conflicts(log)
        c = next(c for c in result if c["field"] == "weight_kg")
        assert "2.8" in c["values"]
        assert "3.1" in c["values"]

    def test_hindi_id_conflict(self):
        """Simulate Hindi worker saying ID 1001 then ID 1002."""
        log = [
            {"field": "beneficiary_id", "value": "1001", "utterance": 0},
            {"field": "beneficiary_id", "value": "1002", "utterance": 1},
        ]
        result = value_conflicts(log)
        assert any(c["field"] == "beneficiary_id" for c in result)


# ─── repeat_vaccines ──────────────────────────────────────────────────────────

class TestRepeatVaccines:
    def test_bcg_already_in_history_is_repeat(self):
        """BCG already in beneficiary history → repeat."""
        history = [{"id": "BCG", "date": "2026-11-21"}]
        result = repeat_vaccines(["BCG"], history)
        assert "BCG" in result

    def test_penta1_vs_penta2_not_duplicate(self):
        """PENTA1 in history does NOT make PENTA2 a repeat — different dose IDs."""
        history = [{"id": "PENTA1", "date": "2026-10-01"}]
        result = repeat_vaccines(["PENTA2"], history)
        assert result == []

    def test_penta1_already_given_is_repeat(self):
        """PENTA1 in history AND PENTA1 given today → repeat."""
        history = [{"id": "PENTA1", "date": "2026-10-01"}]
        result = repeat_vaccines(["PENTA1"], history)
        assert "PENTA1" in result

    def test_penta2_not_in_history_not_repeat(self):
        """PENTA2 not in history → not a repeat."""
        history = [{"id": "PENTA1", "date": "2026-10-01"}]
        result = repeat_vaccines(["PENTA2"], history)
        assert "PENTA2" not in result

    def test_empty_given_today(self):
        history = [{"id": "BCG", "date": "2026-11-21"}]
        assert repeat_vaccines([], history) == []

    def test_empty_history(self):
        assert repeat_vaccines(["BCG"], []) == []

    def test_both_empty(self):
        assert repeat_vaccines([], []) == []

    def test_none_given_today(self):
        history = [{"id": "BCG", "date": "2026-11-21"}]
        assert repeat_vaccines(None, history) == []

    def test_none_history(self):
        assert repeat_vaccines(["BCG"], None) == []

    def test_multiple_repeats(self):
        """Multiple vaccines from given_today are already in history."""
        history = [
            {"id": "BCG", "date": "2026-11-21"},
            {"id": "OPV1", "date": "2026-11-21"},
        ]
        result = repeat_vaccines(["BCG", "OPV1", "PENTA1"], history)
        assert "BCG" in result
        assert "OPV1" in result
        assert "PENTA1" not in result

    def test_td1_in_history_td2_not_repeat(self):
        """TD1 in history does NOT make TD2 a repeat."""
        history = [{"id": "TD1", "date": "2026-09-22"}]
        result = repeat_vaccines(["TD2"], history)
        assert result == []

    def test_opv_zero_vs_opv1_not_duplicate(self):
        """OPV_ZERO and OPV1 are different IDs — no duplicate."""
        history = [{"id": "OPV_ZERO", "date": "2026-11-21"}]
        result = repeat_vaccines(["OPV1"], history)
        assert result == []


# ─── run_all_conflict_checks ──────────────────────────────────────────────────

class TestRunAllConflictChecks:
    def _session(self, symptom_log=None, field_log=None):
        return {
            "symptom_log": symptom_log or [],
            "field_log": field_log or [],
            "_expected_due": [],
        }

    def _draft(self, **kwargs):
        base = {
            "beneficiary_id": "1001",
            "visit_type": "NEWBORN",
            "weight_kg": None,
            "vaccines_given_today": None,
            "vaccines_due_stated": None,
            "next_visit": None,
            "symptoms": None,
        }
        base.update(kwargs)
        return base

    def _ben(self, kind="child", last_weight=3.1, vaccines_given=None):
        return {
            "id": "1001", "name": "Test", "kind": kind,
            "last_weight_kg": last_weight,
            "vaccines_given": vaccines_given or [],
            "last_flags": [],
        }

    def test_symptom_conflict_surfaced(self):
        sym_log = [
            {"sign_id": "NB_FEVER_OR_COLD", "status": "present"},
            {"sign_id": "NB_FEVER_OR_COLD", "status": "absent"},
        ]
        result = run_all_conflict_checks(
            self._session(symptom_log=sym_log),
            self._draft(),
            self._ben(),
        )
        assert "NB_FEVER_OR_COLD" in result["symptom_conflicts"]

    def test_weight_suspicious_flag(self):
        """Weight drop of >30% triggers weight_suspicious."""
        # last_weight=5.0, new=2.0 → ratio 0.4 < 0.7 → suspicious
        result = run_all_conflict_checks(
            self._session(),
            self._draft(weight_kg=2.0),
            self._ben(last_weight=5.0),
        )
        assert result["weight_suspicious"] is True

    def test_repeat_vaccine_flagged(self):
        """BCG already in history → shows up in repeat_vaccines."""
        history = [{"id": "BCG", "date": "2026-11-21"}]
        result = run_all_conflict_checks(
            self._session(),
            self._draft(vaccines_given_today=["BCG"]),
            self._ben(vaccines_given=history),
        )
        assert "BCG" in result["repeat_vaccines"]

    def test_visit_type_conflict_mother_given_newborn(self):
        """NEWBORN visit for a mother → visit_type_conflict True."""
        result = run_all_conflict_checks(
            self._session(),
            self._draft(visit_type="NEWBORN"),
            self._ben(kind="mother"),
        )
        assert result["visit_type_conflict"] is True

    def test_no_conflicts_clean_session(self):
        """Clean session with no contradictions → all conflict lists empty."""
        result = run_all_conflict_checks(
            self._session(),
            self._draft(weight_kg=3.1),
            self._ben(last_weight=3.1),
        )
        assert result["symptom_conflicts"] == []
        assert result["value_conflicts"] == []
        assert result["repeat_vaccines"] == []
        assert result["weight_suspicious"] is False
        assert result["vaccine_mismatch"] == []
        assert result["visit_type_conflict"] is False

    def test_penta1_penta2_not_conflict(self):
        """PENTA1 in history, PENTA2 given today → NOT a repeat."""
        history = [{"id": "PENTA1", "date": "2026-10-01"}]
        result = run_all_conflict_checks(
            self._session(),
            self._draft(vaccines_given_today=["PENTA2"]),
            self._ben(vaccines_given=history),
        )
        assert "PENTA2" not in result["repeat_vaccines"]
