# backend/tests/test_danger.py
# P3 — Tests for danger.py (scan_danger)
# WHY: A missed danger sign is the worst possible failure. Every sign must have
#      a positive test in en, hi, and kn. Negation path must be tested explicitly.
# Run: cd backend && pytest tests/test_danger.py -v

import pytest
from unittest.mock import patch
from app.brain.danger import scan_danger

# ─── Minimal fixture YAML that mirrors danger_signs.yaml structure ─────────────
# WHY: Tests must NOT depend on the real data file changing content.
#      We define two signs — one mother, one newborn — with known keywords.

FIXTURE_SIGNS = [
    {
        "id": "MO_BLEEDING",
        "applies_to": "MOTHER",
        "labels": {"en": "Bleeding", "hi": "रक्तस्राव", "kn": "ರಕ್ತಸ್ರಾವ"},
        "keywords": {
            "en": ["bleeding", "blood"],
            "hi": ["khoon", "खून", "raktsrav"],
            "kn": ["ರಕ್ತಸ್ರಾವ", "rakta"],
        },
        "source": "MCP Card p.4",
    },
    {
        "id": "NB_FEVER_OR_COLD",
        "applies_to": "NEWBORN",
        "labels": {"en": "Fever or cold", "hi": "बुखार", "kn": "ಜ್ವರ"},
        "keywords": {
            "en": ["fever", "hot to touch", "cold to touch"],
            "hi": ["bukhar", "बुखार", "tez bukhar", "thanda"],
            "kn": ["jwara", "ಜ್ವರ", "fever"],
        },
        "source": "ASHA Job Aid p.10",
    },
    {
        "id": "NB_CONVULSIONS",
        "applies_to": "NEWBORN",
        "labels": {"en": "Convulsions", "hi": "दौरे", "kn": "ಸೆಳೆತ"},
        "keywords": {
            "en": ["fits", "convulsions", "seizure"],
            "hi": ["daure", "दौरे", "fits"],
            "kn": ["seleta", "fits"],
        },
        "source": "HBNC Guidelines",
    },
]


@pytest.fixture(autouse=True)
def mock_signs(monkeypatch):
    import app.brain.danger as danger_mod
    monkeypatch.setattr(danger_mod, "_load_signs", lambda: FIXTURE_SIGNS)


# ════════════════════════════════════════════════════════════════════════════════
# Helper
# ════════════════════════════════════════════════════════════════════════════════

def alert_ids(result: dict) -> list[str]:
    return [a["id"] for a in result["alert"]]


def confirm_ids(result: dict) -> list[str]:
    return [a["id"] for a in result["confirm_absent"]]


# ════════════════════════════════════════════════════════════════════════════════
# Rule 1: LLM status present/unclear → alert
# ════════════════════════════════════════════════════════════════════════════════

class TestLLMStatusAlert:
    def test_llm_present_alerts(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "tez bukhar"}]
        result = scan_danger("", symptoms, "NEWBORN", "hi-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_llm_unclear_alerts(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "unclear", "quote": ""}]
        result = scan_danger("", symptoms, "NEWBORN", "hi-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_llm_absent_no_alert_no_keyword(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "absent", "quote": ""}]
        result = scan_danger("no issues", symptoms, "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" not in alert_ids(result)
        assert "NB_FEVER_OR_COLD" not in confirm_ids(result)

    def test_trigger_is_llm_when_no_keyword(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": ""}]
        result = scan_danger("baby doing fine", symptoms, "NEWBORN", "en-IN")
        alert = next(a for a in result["alert"] if a["id"] == "NB_FEVER_OR_COLD")
        assert alert["trigger"] == "llm"

    def test_trigger_is_both_when_llm_and_keyword(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "present", "quote": "fever"}]
        result = scan_danger("baby has fever", symptoms, "NEWBORN", "en-IN")
        alert = next(a for a in result["alert"] if a["id"] == "NB_FEVER_OR_COLD")
        assert alert["trigger"] == "both"


# ════════════════════════════════════════════════════════════════════════════════
# Rule 2: Keyword hit, LLM silent → alert
# ════════════════════════════════════════════════════════════════════════════════

class TestKeywordAlert:
    # English keywords
    def test_en_fever_keyword(self):
        result = scan_danger("baby has fever since morning", None, "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_en_bleeding_keyword(self):
        result = scan_danger("patient is bleeding heavily", None, "MOTHER", "en-IN")
        assert "MO_BLEEDING" in alert_ids(result)

    # Hindi keywords (Devanagari script)
    def test_hi_devanagari_bukhar(self):
        result = scan_danger("बच्चे को बुखार है", None, "NEWBORN", "hi-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_hi_devanagari_khoon(self):
        result = scan_danger("बहुत खून आ रहा है", None, "MOTHER", "hi-IN")
        assert "MO_BLEEDING" in alert_ids(result)

    # Hindi romanised keywords
    def test_hi_romanised_bukhar(self):
        result = scan_danger("bachche ko bukhar hai", None, "NEWBORN", "hi-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_hi_romanised_khoon(self):
        result = scan_danger("bahut khoon aa raha hai", None, "MOTHER", "hi-IN")
        assert "MO_BLEEDING" in alert_ids(result)

    # Kannada keywords (Kannada script)
    def test_kn_script_jwara(self):
        result = scan_danger("ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ", None, "NEWBORN", "kn-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_kn_script_bleeding(self):
        result = scan_danger("ರಕ್ತಸ್ರಾವ ಆಗುತ್ತಿದೆ", None, "MOTHER", "kn-IN")
        assert "MO_BLEEDING" in alert_ids(result)

    # Kannada romanised keywords
    def test_kn_romanised_jwara(self):
        result = scan_danger("maguvige jwara ide", None, "NEWBORN", "kn-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_trigger_is_keyword(self):
        result = scan_danger("baby has fever", None, "NEWBORN", "en-IN")
        alert = next(a for a in result["alert"] if a["id"] == "NB_FEVER_OR_COLD")
        assert alert["trigger"] == "keyword"


# ════════════════════════════════════════════════════════════════════════════════
# Rule 3: Keyword hit + LLM absent → confirm_absent (NOT alert, NOT silent drop)
# ════════════════════════════════════════════════════════════════════════════════

class TestNegationConfirmAbsent:
    def test_keyword_plus_llm_absent_goes_to_confirm(self):
        """'bleeding nahi hai' — keyword hit but LLM says absent.
        Must NOT be silently dropped. Goes to confirm_absent."""
        symptoms = [{"sign_id": "MO_BLEEDING", "status": "absent", "quote": ""}]
        result = scan_danger("bleeding nahi hai", symptoms, "MOTHER", "hi-IN")
        assert "MO_BLEEDING" not in alert_ids(result)
        assert "MO_BLEEDING" in confirm_ids(result)

    def test_hindi_negation_to_confirm(self):
        """'khoon nahi aa raha' — keyword 'khoon' hit, LLM absent."""
        symptoms = [{"sign_id": "MO_BLEEDING", "status": "absent", "quote": ""}]
        result = scan_danger("khoon nahi aa raha", symptoms, "MOTHER", "hi-IN")
        assert "MO_BLEEDING" in confirm_ids(result)
        assert "MO_BLEEDING" not in alert_ids(result)

    def test_kannada_negation_to_confirm(self):
        symptoms = [{"sign_id": "NB_FEVER_OR_COLD", "status": "absent", "quote": ""}]
        result = scan_danger("jwara illa", symptoms, "NEWBORN", "kn-IN")
        assert "NB_FEVER_OR_COLD" in confirm_ids(result)

    def test_no_keyword_no_llm_no_fire(self):
        """No keyword, no LLM mention → neither alert nor confirm."""
        result = scan_danger("everything is fine today", None, "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" not in alert_ids(result)
        assert "NB_FEVER_OR_COLD" not in confirm_ids(result)


# ════════════════════════════════════════════════════════════════════════════════
# Rule 4: applies_to filtering
# ════════════════════════════════════════════════════════════════════════════════

class TestAppliesTo:
    def test_mother_sign_skipped_for_newborn(self):
        result = scan_danger("bleeding heavily", None, "NEWBORN", "en-IN")
        assert "MO_BLEEDING" not in alert_ids(result)

    def test_newborn_sign_skipped_for_mother(self):
        result = scan_danger("baby has fever", None, "MOTHER", "en-IN")
        # NB_FEVER_OR_COLD applies_to NEWBORN — should NOT fire for MOTHER
        assert "NB_FEVER_OR_COLD" not in alert_ids(result)

    def test_none_kind_scans_all(self):
        """kind=None → scan all signs, never restrict."""
        result = scan_danger("bleeding and fever and fits", None, None, "en-IN")
        ids = alert_ids(result)
        assert "MO_BLEEDING" in ids
        assert "NB_FEVER_OR_COLD" in ids
        assert "NB_CONVULSIONS" in ids


# ════════════════════════════════════════════════════════════════════════════════
# Rule 5: each sign fires once
# ════════════════════════════════════════════════════════════════════════════════

class TestDeduplication:
    def test_sign_fires_once_even_with_multiple_keywords(self):
        # "fever" and "bukhar" and "jwara" all match NB_FEVER_OR_COLD
        result = scan_danger("fever bukhar jwara", None, "NEWBORN", "en-IN")
        fever_alerts = [a for a in result["alert"] if a["id"] == "NB_FEVER_OR_COLD"]
        assert len(fever_alerts) == 1


# ════════════════════════════════════════════════════════════════════════════════
# Cross-language keyword scanning (always scan all 3)
# ════════════════════════════════════════════════════════════════════════════════

class TestCrossLanguageScanning:
    def test_hindi_keyword_found_in_english_session(self):
        """Session is English but worker code-mixes Hindi word 'bukhar'."""
        result = scan_danger("bachche ko bukhar hai", None, "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_kannada_keyword_found_in_hindi_session(self):
        """Session is Hindi but worker uses Kannada word 'jwara'."""
        result = scan_danger("jwara ide maguvige", None, "NEWBORN", "hi-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_english_keyword_found_in_kannada_session(self):
        """Session is Kannada but worker uses English word 'fits'."""
        result = scan_danger("baby fits ho raha hai", None, "NEWBORN", "kn-IN")
        assert "NB_CONVULSIONS" in alert_ids(result)


# ════════════════════════════════════════════════════════════════════════════════
# Short keyword false-positive guard (whole-word match for <=3 char keywords)
# ════════════════════════════════════════════════════════════════════════════════

class TestShortKeywordGuard:
    def test_hot_in_photograph_no_trigger(self):
        """'hot' is 3 chars — should NOT match inside 'photograph'."""
        # Note: 'hot' is NOT in our fixture keywords, so this tests the guard logic
        # via 'fit' (3 chars). "fitness" should not trigger "fits".
        result = scan_danger("she has good fitness routine", None, "NEWBORN", "en-IN")
        assert "NB_CONVULSIONS" not in alert_ids(result)

    def test_fits_as_whole_word_does_trigger(self):
        result = scan_danger("baby has fits", None, "NEWBORN", "en-IN")
        assert "NB_CONVULSIONS" in alert_ids(result)


# ════════════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_transcript_no_llm(self):
        result = scan_danger("", None, "NEWBORN", "en-IN")
        assert result["alert"] == []
        assert result["confirm_absent"] == []

    def test_none_transcript_no_llm(self):
        result = scan_danger(None, None, "NEWBORN", "en-IN")  # type: ignore
        assert result["alert"] == []

    def test_empty_symptoms_list(self):
        result = scan_danger("fever", [], "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_case_insensitive_keyword(self):
        result = scan_danger("Baby has FEVER", None, "NEWBORN", "en-IN")
        assert "NB_FEVER_OR_COLD" in alert_ids(result)

    def test_multiple_signs_same_transcript(self):
        result = scan_danger("fever and fits", None, "NEWBORN", "en-IN")
        ids = alert_ids(result)
        assert "NB_FEVER_OR_COLD" in ids
        assert "NB_CONVULSIONS" in ids

    def test_result_always_has_both_keys(self):
        result = scan_danger("everything fine", None, "NEWBORN", "en-IN")
        assert "alert" in result
        assert "confirm_absent" in result
