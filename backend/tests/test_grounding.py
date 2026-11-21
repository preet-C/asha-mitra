# backend/tests/test_grounding.py
# A5 — Tests for brain/grounding.py
#
# Covers field_status() for all 6 fields with:
#   - English, Hindi (Devanagari), and Kannada transcripts
#   - unclear symptom still alerts (via scan_danger, not suppressed by grounding)
#   - not_mentioned stays null (grounding only checks non-null fields)
#   - validator_failed cases
#
# How to run:
#   cd backend
#   pytest tests/test_grounding.py -v
#
# Synthetic data only. No LLM calls. No network.

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from app.brain.grounding import field_status


# ─── Helpers ──────────────────────────────────────────────────────────────────

TODAY = date(2026, 11, 21)

def _draft(**kwargs) -> dict:
    """Build a minimal VisitDraft with defaults None."""
    base = {
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
    base.update(kwargs)
    return base


def _ben(kind="child", last_weight=3.1) -> dict:
    return {"id": "1001", "name": "Arjun", "kind": kind, "last_weight_kg": last_weight,
            "vaccines_given": [], "last_flags": []}


def _run(draft, transcript, beneficiary=None, lang="en-IN"):
    """Freeze today and call field_status."""
    with patch("app.brain.grounding.date") as mock_date:
        mock_date.today.return_value = TODAY
        return field_status(draft, transcript, beneficiary, lang)


# ─── beneficiary_id ───────────────────────────────────────────────────────────

class TestBeneficiaryId:
    def test_grounded_when_found_in_repo(self):
        d = _draft(beneficiary_id="1001")
        result = _run(d, "ID 1001", beneficiary=_ben())
        assert result["beneficiary_id"] == "grounded"

    def test_validator_failed_when_not_in_repo(self):
        d = _draft(beneficiary_id="9999")
        result = _run(d, "ID 9999", beneficiary=None)
        assert result["beneficiary_id"] == "validator_failed"

    def test_validator_failed_when_not_4_digits(self):
        d = _draft(beneficiary_id="123")
        result = _run(d, "ID 123", beneficiary=None)
        assert result["beneficiary_id"] == "validator_failed"

    def test_null_id_not_in_result(self):
        """Not-mentioned field (null) must not appear in result."""
        d = _draft(beneficiary_id=None)
        result = _run(d, "some transcript")
        assert "beneficiary_id" not in result


# ─── weight_kg ────────────────────────────────────────────────────────────────

class TestWeightKg:
    def test_grounded_digit_in_en_transcript(self):
        d = _draft(weight_kg=2.8)
        result = _run(d, "weight is 2.8 kg")
        assert result["weight_kg"] == "grounded"

    def test_grounded_digit_in_hindi_transcript(self):
        """Hindi transcript with digit: ID 1001, वज़न 3.5 किलो"""
        d = _draft(weight_kg=3.5)
        result = _run(d, "ID 1001, वज़न 3.5 किलो", lang="hi-IN")
        assert result["weight_kg"] == "grounded"

    def test_grounded_kannada_transcript_with_digit(self):
        """Kannada transcript with digit."""
        d = _draft(weight_kg=4.2)
        result = _run(d, "ತೂಕ 4.2 ಕೆಜಿ", lang="kn-IN")
        assert result["weight_kg"] == "grounded"

    def test_ungrounded_when_no_number_in_transcript(self):
        """LLM produced weight but transcript has no matching digit."""
        d = _draft(weight_kg=2.8)
        result = _run(d, "ID 1001 newborn visit")
        assert result["weight_kg"] == "ungrounded"

    def test_validator_failed_weight_out_of_child_range(self):
        """Weight 0.5 kg is below child minimum (1 kg)."""
        d = _draft(weight_kg=0.5)
        result = _run(d, "weight 0.5 kg")
        assert result["weight_kg"] == "validator_failed"

    def test_validator_failed_weight_out_of_mother_range(self):
        """Weight 200 kg exceeds mother maximum (120 kg)."""
        d = _draft(weight_kg=200.0, visit_type="ANC")
        result = _run(d, "weight 200 kg")
        assert result["weight_kg"] == "validator_failed"

    def test_grounded_gram_form_in_transcript(self):
        """2800 gram form in transcript for 2.8 kg."""
        d = _draft(weight_kg=2.8)
        result = _run(d, "bache ka wajan 2800 gram hai")
        assert result["weight_kg"] == "grounded"

    def test_null_weight_not_in_result(self):
        d = _draft(weight_kg=None)
        result = _run(d, "some text")
        assert "weight_kg" not in result


# ─── vaccines_given_today ─────────────────────────────────────────────────────

class TestVaccines:
    def test_grounded_penta1_en(self):
        d = _draft(vaccines_given_today=["PENTA1"])
        result = _run(d, "penta one given today")
        assert result["vaccines_given_today"] == "grounded"

    def test_grounded_penta1_hindi(self):
        """Hindi alias for PENTA1."""
        d = _draft(vaccines_given_today=["PENTA1"])
        result = _run(d, "पेंटा एक आज लगाया", lang="hi-IN")
        assert result["vaccines_given_today"] == "grounded"

    def test_grounded_penta1_kannada(self):
        """Kannada alias for PENTA1."""
        d = _draft(vaccines_given_today=["PENTA1"])
        result = _run(d, "ಪೆಂಟಾ ಒಂದು ಇಂದು ಹಾಕಿದೆ", lang="kn-IN")
        assert result["vaccines_given_today"] == "grounded"

    def test_ungrounded_vaccine_not_in_transcript(self):
        """PENTA2 not mentioned in transcript → ungrounded."""
        d = _draft(vaccines_given_today=["PENTA2"])
        result = _run(d, "today we visited the child")
        assert result["vaccines_given_today"] == "ungrounded"

    def test_penta1_vs_penta2_different_grounding(self):
        """PENTA1 alias in transcript: PENTA1 is grounded, PENTA2 is not."""
        d = _draft(vaccines_given_today=["PENTA1", "PENTA2"])
        # penta one is in transcript → PENTA1 found; penta two is NOT
        result = _run(d, "penta one was given")
        # Mixed: PENTA2 not found → overall ungrounded
        assert result["vaccines_given_today"] == "ungrounded"

    def test_bcg_grounded_en(self):
        """BCG alias match."""
        d = _draft(vaccines_given_today=["BCG"])
        result = _run(d, "bcg injection given at birth")
        assert result["vaccines_given_today"] == "grounded"

    def test_td1_grounded_hindi(self):
        """TT injection alias in Hindi."""
        d = _draft(vaccines_given_today=["TD1"])
        result = _run(d, "टीटी इंजेक्शन एक दिया", lang="hi-IN")
        assert result["vaccines_given_today"] == "grounded"

    def test_null_vaccines_not_in_result(self):
        d = _draft(vaccines_given_today=None)
        result = _run(d, "some text")
        assert "vaccines_given_today" not in result


# ─── next_visit ───────────────────────────────────────────────────────────────

class TestNextVisit:
    def test_grounded_with_digit_in_transcript(self):
        spec = {"kind": "relative_days", "n": 15}
        d = _draft(next_visit=spec)
        result = _run(d, "next visit in 15 days")
        assert result["next_visit"] == "grounded"

    def test_grounded_month_name_in_hindi(self):
        spec = {"kind": "absolute", "day": 5, "month": 12, "year": 2026}
        d = _draft(next_visit=spec)
        result = _run(d, "अगला विज़िट दिसंबर पाँच", lang="hi-IN")
        assert result["next_visit"] == "grounded"

    def test_grounded_weekday_in_transcript(self):
        spec = {"kind": "weekday", "weekday": 1, "which": "next"}
        d = _draft(next_visit=spec)
        result = _run(d, "next monday visit")
        assert result["next_visit"] == "grounded"

    def test_ungrounded_no_date_clue(self):
        """Spec exists but transcript has no temporal marker."""
        spec = {"kind": "relative_days", "n": 7}
        d = _draft(next_visit=spec)
        result = _run(d, "newborn visit everything fine")
        # No digits or time words → ungrounded
        assert result["next_visit"] == "ungrounded"

    def test_validator_failed_past_date(self):
        """Absolute date in the past → validator_failed."""
        # Date is 2026-01-01 which is before TODAY (2026-11-21)
        spec = {"kind": "absolute", "day": 1, "month": 1, "year": 2026}
        d = _draft(next_visit=spec)
        result = _run(d, "visit on january 1")
        assert result["next_visit"] == "validator_failed"

    def test_null_next_visit_not_in_result(self):
        d = _draft(next_visit=None)
        result = _run(d, "some text")
        assert "next_visit" not in result


# ─── visit_type ───────────────────────────────────────────────────────────────

class TestVisitType:
    def test_grounded_child_newborn(self):
        """NEWBORN is valid for a child beneficiary."""
        d = _draft(visit_type="NEWBORN")
        result = _run(d, "newborn visit", beneficiary=_ben(kind="child"))
        assert result["visit_type"] == "grounded"

    def test_validator_failed_anc_for_child(self):
        """ANC visit for a child beneficiary is a conflict."""
        d = _draft(visit_type="ANC")
        result = _run(d, "anc checkup", beneficiary=_ben(kind="child"))
        assert result["visit_type"] == "validator_failed"

    def test_grounded_anc_for_mother(self):
        """ANC is valid for mother."""
        d = _draft(visit_type="ANC")
        result = _run(d, "anc checkup", beneficiary={"id": "1009", "kind": "mother",
                                                      "last_weight_kg": 58.0,
                                                      "vaccines_given": [], "last_flags": []})
        assert result["visit_type"] == "grounded"

    def test_grounded_no_beneficiary_no_conflict(self):
        """When beneficiary not loaded, check_visit_type returns False → grounded."""
        d = _draft(visit_type="IMMUNISATION")
        result = _run(d, "immunisation visit", beneficiary=None)
        assert result["visit_type"] == "grounded"

    def test_null_visit_type_not_in_result(self):
        d = _draft(visit_type=None)
        result = _run(d, "some text")
        assert "visit_type" not in result


# ─── symptoms ─────────────────────────────────────────────────────────────────

class TestSymptoms:
    def test_unclear_symptom_grounded_when_quote_in_transcript(self):
        """SAFETY: unclear symptom is grounded when quote appears. Alert still fires via scan_danger."""
        syms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "unclear", "quote": "tez bukhar"}]
        d = _draft(symptoms=syms)
        result = _run(d, "bache ko tez bukhar hai")
        # Grounding says grounded — but this NEVER suppresses the alert
        assert result["symptoms"] == "grounded"

    def test_ungrounded_when_quote_not_in_transcript(self):
        """Quote not in transcript → ungrounded (ask worker to repeat)."""
        syms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "tez bukhar"}]
        d = _draft(symptoms=syms)
        # Transcript doesn't contain the quote
        result = _run(d, "ID 1001, weight 3 kg, next visit December")
        assert result["symptoms"] == "ungrounded"

    def test_hindi_symptom_quote_grounded(self):
        """Hindi Devanagari quote in Devanagari transcript → grounded."""
        syms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "बुखार"}]
        d = _draft(symptoms=syms)
        result = _run(d, "बच्चे को तेज़ बुखार है आज से", lang="hi-IN")
        assert result["symptoms"] == "grounded"

    def test_kannada_symptom_quote_grounded(self):
        """Kannada quote in Kannada transcript → grounded."""
        syms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "ಜ್ವರ"}]
        d = _draft(symptoms=syms)
        result = _run(d, "ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ", lang="kn-IN")
        assert result["symptoms"] == "grounded"

    def test_absent_symptom_ungrounded(self):
        """absent symptom (no quote to verify) → ungrounded. Alert is NOT suppressed."""
        syms = [{"sign_id": "MO_BLEEDING", "status": "absent", "quote": ""}]
        d = _draft(symptoms=syms)
        result = _run(d, "bleeding nahi hai")
        # absent with no quote → ungrounded; that's ok, dialogue will ask confirm_absent
        assert result["symptoms"] == "ungrounded"

    def test_null_symptoms_not_in_result(self):
        """Null symptoms (not_mentioned) must NOT appear in result."""
        d = _draft(symptoms=None)
        result = _run(d, "some transcript")
        assert "symptoms" not in result


# ─── not_mentioned stays null ─────────────────────────────────────────────────

class TestNotMentionedStaysNull:
    def test_all_null_draft_returns_empty_result(self):
        """All-null draft → field_status returns {} (not_mentioned ≠ absent)."""
        d = _draft()
        result = _run(d, "some text")
        # No field should appear since all are null
        for field in ("beneficiary_id", "weight_kg", "vaccines_given_today",
                      "next_visit", "visit_type", "symptoms"):
            assert field not in result

    def test_only_non_null_fields_appear(self):
        """Only non-null fields appear in result."""
        d = _draft(weight_kg=3.1, visit_type="NEWBORN")
        result = _run(d, "weight 3.1 kg", beneficiary=_ben())
        # beneficiary_id is null → should NOT be in result
        assert "beneficiary_id" not in result
        # weight_kg is non-null → should be in result
        assert "weight_kg" in result
        assert "visit_type" in result


# ─── Unclear symptom still alerts ─────────────────────────────────────────────

class TestSymptomAlertNotSuppressed:
    def test_unclear_symptom_grounding_does_not_suppress_scan_danger(self):
        """Grounding is ungrounded for a symptom → scan_danger still alerts.

        This test verifies the design contract: field_status() does NOT call
        scan_danger() and does NOT touch session flags. The alert comes from
        dialogue.py calling scan_danger() separately.

        We verify here that field_status() returns a status (not None) for
        an unclear symptom, without touching the scan_danger result at all.
        """
        syms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "unclear", "quote": ""}]
        d = _draft(symptoms=syms)
        result = _run(d, "bache ko kuch hua hai")
        # field_status returns a status for symptoms (ungrounded here since no quote match)
        assert "symptoms" in result
        # Crucially, it's NOT "suppress_alert" or any such thing
        assert result["symptoms"] in {"grounded", "ungrounded", "ambiguous", "validator_failed"}
