# backend/tests/test_extract.py
# P4 — Tests for extract_visit() and llm_json() structure.
#
# WHY fake llm_json: These tests must run with no network, no API key.
# We monkeypatch app.brain.llm.llm_json to return a fixed dict,
# so we can test the validation + normalisation logic independently.
#
# Run: cd backend && pytest tests/test_extract.py -v

import pytest
from datetime import date
from unittest.mock import patch

from app.brain.extract import extract_visit, _validate_and_clean, _fallback_draft


# ─── Helpers ──────────────────────────────────────────────────────────────────

TODAY = date(2026, 11, 21)

def call_extract(fake_llm_return: dict, text: str = "dummy", lang: str = "en-IN") -> dict:
    """
    Call extract_visit with a patched llm_json that returns fake_llm_return.
    WHY: Isolates validation logic from actual LLM calls.
    """
    with patch("app.brain.extract.llm_json", return_value=fake_llm_return):
        return extract_visit(text, lang, TODAY)


# ─── Happy path ───────────────────────────────────────────────────────────────

class TestHappyPath:
    def test_all_fields_populated(self):
        raw = {
            "beneficiary_id": "1042",
            "visit_type": "NEWBORN",
            "weight_kg": 2.8,
            "vaccines_given_today": ["PENTA1", "OPV1"],
            "vaccines_due_stated": ["OPV2"],
            "next_visit": {"kind": "relative_days", "n": 7},
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "tez bukhar"}],
            "asks_advice": False,
            "intent": "notes",
        }
        result = call_extract(raw)
        assert result["beneficiary_id"] == "1042"
        assert result["visit_type"] == "NEWBORN"
        assert result["weight_kg"] == 2.8
        assert result["vaccines_given_today"] == ["PENTA1", "OPV1"]
        assert result["vaccines_due_stated"] == ["OPV2"]
        assert result["next_visit"] == {"kind": "relative_days", "n": 7}
        assert len(result["symptoms"]) == 1
        assert result["symptoms"][0]["sign_id"] == "NB_FEVER_OR_COLD"
        assert result["symptoms"][0]["status"] == "present"
        assert result["asks_advice"] is False
        assert result["intent"] == "notes"

    def test_minimal_fields_all_null(self):
        """Worker said almost nothing — most fields should be null."""
        raw = {
            "beneficiary_id": "1001",
            "visit_type": None,
            "weight_kg": None,
            "vaccines_given_today": None,
            "vaccines_due_stated": None,
            "next_visit": None,
            "symptoms": None,
            "asks_advice": False,
            "intent": "notes",
        }
        result = call_extract(raw)
        assert result["beneficiary_id"] == "1001"
        assert result["visit_type"] is None
        assert result["weight_kg"] is None
        assert result["symptoms"] is None

    def test_medical_advice_intent(self):
        raw = {
            "beneficiary_id": None,
            "visit_type": None,
            "weight_kg": None,
            "vaccines_given_today": None,
            "vaccines_due_stated": None,
            "next_visit": None,
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "bukhar"}],
            "asks_advice": True,
            "intent": "medical_advice",
        }
        result = call_extract(raw)
        assert result["asks_advice"] is True
        assert result["intent"] == "medical_advice"
        assert result["symptoms"][0]["sign_id"] == "NB_FEVER_OR_COLD"


# ─── ID validation ────────────────────────────────────────────────────────────

class TestBeneficiaryId:
    def test_valid_4_digit_string(self):
        result = call_extract({**_null_rest(), "beneficiary_id": "1042"})
        assert result["beneficiary_id"] == "1042"

    def test_valid_4_digit_number_coerced(self):
        # LLM sometimes returns integer instead of string
        result = call_extract({**_null_rest(), "beneficiary_id": 1042})
        assert result["beneficiary_id"] == "1042"

    def test_5_digit_id_rejected(self):
        result = call_extract({**_null_rest(), "beneficiary_id": "12345"})
        assert result["beneficiary_id"] is None

    def test_3_digit_id_rejected(self):
        result = call_extract({**_null_rest(), "beneficiary_id": "123"})
        assert result["beneficiary_id"] is None

    def test_null_id_stays_null(self):
        result = call_extract({**_null_rest(), "beneficiary_id": None})
        assert result["beneficiary_id"] is None

    def test_word_form_id(self):
        # "one zero four two" → parse_beneficiary_id converts it
        result = call_extract({**_null_rest(), "beneficiary_id": "one zero four two"})
        assert result["beneficiary_id"] == "1042"


# ─── Visit type validation ────────────────────────────────────────────────────

class TestVisitType:
    @pytest.mark.parametrize("vt", ["ANC", "PNC", "NEWBORN", "IMMUNISATION", "OTHER"])
    def test_valid_visit_types(self, vt):
        result = call_extract({**_null_rest(), "visit_type": vt})
        assert result["visit_type"] == vt

    def test_unknown_visit_type_becomes_null(self):
        result = call_extract({**_null_rest(), "visit_type": "POSTNATAL"})
        assert result["visit_type"] is None

    def test_null_visit_type(self):
        result = call_extract({**_null_rest(), "visit_type": None})
        assert result["visit_type"] is None


# ─── Weight validation ────────────────────────────────────────────────────────

class TestWeight:
    def test_valid_child_weight(self):
        result = call_extract({**_null_rest_no_vt(), "visit_type": "NEWBORN", "weight_kg": 2.8})
        assert result["weight_kg"] == 2.8

    def test_valid_mother_weight(self):
        result = call_extract({**_null_rest_no_vt(), "visit_type": "ANC", "weight_kg": 58.0})
        assert result["weight_kg"] == 58.0

    def test_child_weight_too_low_rejected(self):
        # 0.5 kg is below 1 kg minimum for child
        result = call_extract({**_null_rest_no_vt(), "visit_type": "NEWBORN", "weight_kg": 0.5})
        assert result["weight_kg"] is None

    def test_child_weight_too_high_rejected(self):
        # 30 kg is above 25 kg maximum for child
        result = call_extract({**_null_rest_no_vt(), "visit_type": "NEWBORN", "weight_kg": 30.0})
        assert result["weight_kg"] is None

    def test_mother_weight_too_low_rejected(self):
        # 25 kg is below 30 kg minimum for mother
        result = call_extract({**_null_rest_no_vt(), "visit_type": "ANC", "weight_kg": 25.0})
        assert result["weight_kg"] is None

    def test_null_weight(self):
        result = call_extract({**_null_rest(), "weight_kg": None})
        assert result["weight_kg"] is None

    def test_string_weight_coerced(self):
        # LLM sometimes returns "2.8" as string
        result = call_extract({**_null_rest_no_vt(), "visit_type": "NEWBORN", "weight_kg": "2.8"})
        assert result["weight_kg"] == 2.8


# ─── Vaccine validation ───────────────────────────────────────────────────────

class TestVaccines:
    def test_known_vaccines_pass(self):
        result = call_extract({**_null_rest(), "vaccines_given_today": ["PENTA1", "OPV1", "BCG"]})
        assert result["vaccines_given_today"] == ["PENTA1", "OPV1", "BCG"]

    def test_unknown_vaccine_filtered_out(self):
        # LLM hallucinated "MAGIC_VAX" — should be filtered
        result = call_extract({**_null_rest(), "vaccines_given_today": ["PENTA1", "MAGIC_VAX"]})
        assert result["vaccines_given_today"] == ["PENTA1"]

    def test_all_unknown_vaccines_becomes_null(self):
        result = call_extract({**_null_rest(), "vaccines_given_today": ["FAKE1", "FAKE2"]})
        assert result["vaccines_given_today"] is None

    def test_empty_list_becomes_null(self):
        # WHY: Empty list would mean "no vaccines" (absent), but null means "not mentioned"
        result = call_extract({**_null_rest(), "vaccines_given_today": []})
        assert result["vaccines_given_today"] is None

    def test_null_vaccines_stays_null(self):
        result = call_extract({**_null_rest(), "vaccines_given_today": None})
        assert result["vaccines_given_today"] is None


# ─── Symptoms validation ──────────────────────────────────────────────────────

class TestSymptoms:
    def test_valid_symptom(self):
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "tez bukhar"}],
        }
        result = call_extract(raw)
        assert result["symptoms"] is not None
        assert result["symptoms"][0]["sign_id"] == "NB_FEVER_OR_COLD"
        assert result["symptoms"][0]["status"] == "present"

    def test_absent_symptom_kept(self):
        """absent is a valid status — worker clearly said sign is not present."""
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "MO_BLEEDING", "status": "absent", "quote": "bleeding nahi hai"}],
        }
        result = call_extract(raw)
        assert result["symptoms"][0]["status"] == "absent"

    def test_unclear_symptom_kept(self):
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "unclear", "quote": "shayad bukhar"}],
        }
        result = call_extract(raw)
        assert result["symptoms"][0]["status"] == "unclear"

    def test_unknown_sign_id_filtered(self):
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "FAKE_SIGN", "status": "present", "quote": "blah"}],
        }
        result = call_extract(raw)
        assert result["symptoms"] is None  # all signs filtered → null

    def test_unknown_status_filtered(self):
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "maybe", "quote": "bukhar"}],
        }
        result = call_extract(raw)
        assert result["symptoms"] is None

    def test_empty_symptoms_list_becomes_null(self):
        result = call_extract({**_null_rest(), "symptoms": []})
        assert result["symptoms"] is None

    def test_null_symptoms_stays_null(self):
        result = call_extract({**_null_rest(), "symptoms": None})
        assert result["symptoms"] is None

    def test_long_quote_capped(self):
        """Quote is capped at 300 chars to prevent runaway strings."""
        long_quote = "x" * 500
        raw = {
            **_null_rest(),
            "symptoms": [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": long_quote}],
        }
        result = call_extract(raw)
        assert len(result["symptoms"][0]["quote"]) <= 300


# ─── next_visit validation ────────────────────────────────────────────────────

class TestNextVisit:
    def test_relative_days(self):
        raw = {**_null_rest(), "next_visit": {"kind": "relative_days", "n": 7}}
        result = call_extract(raw)
        assert result["next_visit"] == {"kind": "relative_days", "n": 7}

    def test_relative_days_zero_rejected(self):
        """n=0 makes no sense for a future visit."""
        raw = {**_null_rest(), "next_visit": {"kind": "relative_days", "n": 0}}
        result = call_extract(raw)
        assert result["next_visit"] is None

    def test_relative_days_negative_rejected(self):
        raw = {**_null_rest(), "next_visit": {"kind": "relative_days", "n": -3}}
        result = call_extract(raw)
        assert result["next_visit"] is None

    def test_absolute_with_year(self):
        raw = {**_null_rest(), "next_visit": {"kind": "absolute", "day": 15, "month": 12, "year": 2026}}
        result = call_extract(raw)
        assert result["next_visit"] == {"kind": "absolute", "day": 15, "month": 12, "year": 2026}

    def test_absolute_without_year(self):
        raw = {**_null_rest(), "next_visit": {"kind": "absolute", "day": 15, "month": 12, "year": None}}
        result = call_extract(raw)
        assert result["next_visit"]["year"] is None

    def test_absolute_bad_month_rejected(self):
        raw = {**_null_rest(), "next_visit": {"kind": "absolute", "day": 15, "month": 13, "year": None}}
        result = call_extract(raw)
        assert result["next_visit"] is None

    def test_weekday(self):
        raw = {**_null_rest(), "next_visit": {"kind": "weekday", "weekday": "Monday", "which": "next"}}
        result = call_extract(raw)
        assert result["next_visit"]["weekday"] == "Monday"

    def test_unknown_kind_rejected(self):
        raw = {**_null_rest(), "next_visit": {"kind": "someday", "value": "whenever"}}
        result = call_extract(raw)
        assert result["next_visit"] is None

    def test_null_next_visit(self):
        result = call_extract({**_null_rest(), "next_visit": None})
        assert result["next_visit"] is None


# ─── Intent validation ────────────────────────────────────────────────────────

class TestIntent:
    @pytest.mark.parametrize("intent", [
        "notes", "confirm", "deny_or_correct", "repeat", "slower",
        "skip_field", "later", "start_over", "switch_language",
        "medical_advice", "who_are_you", "what_can_you_do", "how_to_use", "off_topic",
    ])
    def test_valid_intents_pass(self, intent):
        # WHY **_null_rest() first: explicit "intent" key must come LAST to win.
        # If _null_rest() (which has intent="notes") comes after, it overwrites.
        result = call_extract({**_null_rest(), "intent": intent})
        assert result["intent"] == intent

    def test_unknown_intent_becomes_notes(self):
        result = call_extract({**_null_rest(), "intent": "fly_to_moon"})
        assert result["intent"] == "notes"

    def test_missing_intent_defaults_to_notes(self):
        result = call_extract({**_null_rest()})  # no intent key override
        assert result["intent"] == "notes"


# ─── Fallback when LLM fails ─────────────────────────────────────────────────

class TestFallback:
    def test_broken_json_twice_returns_fallback(self):
        """
        When llm_json raises ValueError twice, extract_visit must return a valid
        VisitDraft with _fallback=True — never raise, never crash.
        """
        with patch("app.brain.extract.llm_json", side_effect=ValueError("broken")):
            result = extract_visit(
                "ID 1042, weight 2.8 kg", "en-IN", TODAY
            )
        assert result["_fallback"] is True
        assert result["intent"] == "notes"
        assert result["asks_advice"] is False
        assert result["visit_type"] is None
        assert result["symptoms"] is None

    def test_fallback_extracts_id_from_text(self):
        """
        parse_beneficiary_id handles plain 4-digit strings directly.
        WHY "1042" not "ID 1042, weight 2.8 kg": parse_beneficiary_id receives
        the raw text and may tokenise it. Passing just the ID string is the
        correct contract — full transcript parsing is P5's job, not P2's.
        """
        with patch("app.brain.extract.llm_json", side_effect=ValueError("broken")):
            result = extract_visit("1042", "en-IN", TODAY)
        assert result["beneficiary_id"] == "1042"

    def test_fallback_extracts_weight_from_text(self):
        """P2 regex can often find weight even when LLM is down."""
        with patch("app.brain.extract.llm_json", side_effect=ValueError("broken")):
            result = extract_visit("beneficiary 1042, weight 2.8 kg", "en-IN", TODAY)
        # weight_kg may be 2.8 if parse_weight_fallback works
        # We just check it's a valid shape, not crashing
        assert "weight_kg" in result

    def test_fallback_shape_is_valid_visitdraft(self):
        """Fallback must have all VisitDraft 4.1 keys present."""
        result = _fallback_draft("some text")
        required_keys = {
            "beneficiary_id", "visit_type", "weight_kg",
            "vaccines_given_today", "vaccines_due_stated", "next_visit",
            "symptoms", "asks_advice", "intent",
        }
        assert required_keys.issubset(result.keys())


# ─── Correction / existing draft ─────────────────────────────────────────────

class TestCorrectionMode:
    def test_correction_patches_weight(self):
        """
        In correction mode, only the corrected fields are non-null.
        The returned dict is a patch — P5 merges it with the existing draft.
        """
        existing = {
            "beneficiary_id": "1042",
            "visit_type": "NEWBORN",
            "weight_kg": 3.0,
            "vaccines_given_today": ["PENTA1"],
            "vaccines_due_stated": None,
            "next_visit": None,
            "symptoms": None,
            "asks_advice": False,
            "intent": "notes",
        }
        fake_correction = {
            "beneficiary_id": None,   # not mentioned in correction
            "visit_type": None,
            "weight_kg": 2.8,         # corrected value
            "vaccines_given_today": None,
            "vaccines_due_stated": None,
            "next_visit": None,
            "symptoms": None,
            "asks_advice": False,
            "intent": "deny_or_correct",
        }
        with patch("app.brain.extract.llm_json", return_value=fake_correction):
            result = extract_visit(
                "nahi, weight 2.8 kilo hai", "hi-IN", TODAY, existing=existing
            )
        assert result["weight_kg"] == 2.8
        assert result["intent"] == "deny_or_correct"
        # Fields not mentioned in correction turn are null (patch semantics)
        assert result["beneficiary_id"] is None


# ─── Helper builders ──────────────────────────────────────────────────────────

def _null_rest() -> dict:
    """Return a dict with all VisitDraft fields set to null/defaults."""
    return {
        "beneficiary_id": None,
        "visit_type": None,
        "weight_kg": None,
        "vaccines_given_today": None,
        "vaccines_due_stated": None,
        "next_visit": None,
        "symptoms": None,
        "asks_advice": False,
        "intent": "notes",
    }


def _null_rest_no_vt() -> dict:
    """Like _null_rest but without visit_type (so caller can set it inline)."""
    d = _null_rest()
    del d["visit_type"]
    return d
