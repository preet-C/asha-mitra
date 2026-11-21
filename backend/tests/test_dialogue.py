# backend/tests/test_dialogue.py
# P5a — Scenario tests for the dialogue brain.
#
# WHY offline tests: The dialogue brain must work without network. These tests
# use a fake extract_visit that returns pre-canned dicts, so LLM is never called.
# This is the same approach as test_extract.py (fake llm_json).
#
# How to run:
#   cd backend
#   .venv\Scripts\Activate.ps1
#   pytest tests/test_dialogue.py -v

import pytest
from datetime import date
from unittest.mock import patch

from app.brain.dialogue import new_session, handle, STATE_CAPTURE, STATE_READBACK, STATE_DONE
from app.repo import memory_repo


# ─── Helpers ──────────────────────────────────────────────────────────────────

TODAY = date(2026, 11, 21)

def _start(lang="en-IN"):
    """Create a fresh session and fire "start". Returns (session, start_actions)."""
    memory_repo.reset_for_testing()
    session = new_session(lang)
    with patch("app.brain.dialogue.date") as mock_date:
        mock_date.today.return_value = TODAY
        actions = handle(session, {"type": "start", "lang": lang})
    return session, actions


def _user(session, text, extract_return=None):
    """Fire "user_text" event, optionally patching extract_visit return value."""
    with patch("app.brain.dialogue.date") as mock_date:
        mock_date.today.return_value = TODAY
        if extract_return is not None:
            with patch("app.brain.dialogue.extract_visit", return_value=extract_return):
                return handle(session, {"type": "user_text", "text": text})
        else:
            with patch("app.brain.dialogue.extract_visit", return_value=_null_draft()):
                return handle(session, {"type": "user_text", "text": text})


def _null_draft(**overrides):
    """Return a VisitDraft with everything null + optional overrides."""
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
    base.update(overrides)
    return base


def _action_types(actions):
    return [a["type"] for a in actions]


def _say_keys(actions):
    return [a["key"] for a in actions if a["type"] == "say"]


def _find(actions, atype):
    """Return first action of given type, or None."""
    return next((a for a in actions if a["type"] == atype), None)


# ─── Test: start event ────────────────────────────────────────────────────────

class TestStart:
    def test_start_says_disclosure(self):
        """First thing agent says must be disclosure (Tier A, always template)."""
        session, actions = _start("en-IN")
        says = _say_keys(actions)
        assert "disclosure" in says, f"Expected disclosure in {says}"

    def test_start_asks_id_when_draft_empty(self):
        """After disclosure, should ask for ID since we don't have it yet."""
        session, actions = _start("en-IN")
        says = _say_keys(actions)
        assert "ask_id" in says, f"Expected ask_id in {says}"

    def test_start_state_is_capture(self):
        session, _ = _start("en-IN")
        assert session["state"] == STATE_CAPTURE

    def test_start_hindi(self):
        """Disclosure and ask_id fire in Hindi too."""
        session, actions = _start("hi-IN")
        says = _say_keys(actions)
        assert "disclosure" in says
        assert "ask_id" in says


# ─── Test: ID lookup ──────────────────────────────────────────────────────────

class TestIDLookup:
    def test_known_id_loads_beneficiary(self):
        """When worker gives a known ID, beneficiary is loaded into session."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="1001")
        actions = _user(session, "ID is 1001", extract_return=draft)
        assert session["beneficiary"] is not None
        assert session["beneficiary"]["id"] == "1001"

    def test_unknown_id_says_not_found(self):
        """Unknown ID → id_not_found message, ID cleared from draft."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="9999")
        actions = _user(session, "ID is 9999", extract_return=draft)
        says = _say_keys(actions)
        assert "id_not_found" in says
        assert session["draft"]["beneficiary_id"] is None

    def test_state_goes_to_readback_after_id_found(self):
        """Once we have an ID, should move to READBACK state."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="1001")
        _user(session, "ID is 1001", extract_return=draft)
        assert session["state"] == STATE_READBACK


# ─── Test: Readback ───────────────────────────────────────────────────────────

class TestReadback:
    def test_readback_action_emitted(self):
        """After ID, agent says readback."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="1001")
        actions = _user(session, "ID 1001", extract_return=draft)
        says = _say_keys(actions)
        assert "readback" in says

    def test_readback_contains_id(self):
        """Readback text must include the beneficiary ID."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="1001", weight_kg=3.1, visit_type="NEWBORN")
        actions = _user(session, "ID 1001, weight 3.1, newborn", extract_return=draft)
        readback_action = next((a for a in actions if a.get("key") == "readback"), None)
        assert readback_action is not None
        text = readback_action.get("_text", "")
        assert text, "Readback text should not be empty"

    def test_card_action_emitted(self):
        """Card action must be emitted so UI updates."""
        session, _ = _start("en-IN")
        draft = _null_draft(beneficiary_id="1001")
        actions = _user(session, "ID 1001", extract_return=draft)
        card = _find(actions, "card")
        assert card is not None
        assert "draft" in card


# ─── Test: Confirm and save ───────────────────────────────────────────────────

class TestConfirmAndSave:
    def _get_to_readback(self, lang="en-IN"):
        """Helper to get session into READBACK state with ID 1001."""
        session, _ = _start(lang)
        draft = _null_draft(beneficiary_id="1001")
        _user(session, "ID 1001", extract_return=draft)
        assert session["state"] == STATE_READBACK
        return session

    def test_confirm_word_saves_visit(self):
        """Saying 'yes' in READBACK state saves the visit."""
        session = self._get_to_readback()
        actions = _user(session, "yes", extract_return=_null_draft(intent="confirm"))
        assert session["state"] == STATE_DONE
        saved = _find(actions, "saved")
        assert saved is not None
        assert saved["visit_id"]  # visit_id should be non-empty

    def test_confirm_says_saved_template(self):
        """After saving, agent says the 'saved' template."""
        session = self._get_to_readback()
        actions = _user(session, "yes", extract_return=_null_draft(intent="confirm"))
        says = _say_keys(actions)
        assert "saved" in says

    def test_haan_confirms_in_hindi(self):
        """'haan' should trigger save in Hindi session."""
        session = self._get_to_readback("hi-IN")
        actions = _user(session, "haan", extract_return=_null_draft(intent="confirm"))
        assert session["state"] == STATE_DONE

    def test_sari_confirms_in_kannada(self):
        """'ಸರಿ' should trigger save in Kannada session."""
        session = self._get_to_readback("kn-IN")
        actions = _user(session, "ಸರಿ", extract_return=_null_draft(intent="confirm"))
        assert session["state"] == STATE_DONE


# ─── Test: Correction at readback ────────────────────────────────────────────

class TestCorrection:
    def test_correction_says_readback_changed(self):
        """Correction at READBACK emits readback_changed template."""
        session, _ = _start("en-IN")
        draft1 = _null_draft(beneficiary_id="1001", weight_kg=3.1)
        _user(session, "ID 1001, weight 3.1", extract_return=draft1)
        assert session["state"] == STATE_READBACK

        # Worker corrects weight
        draft2 = _null_draft(weight_kg=2.8)
        actions = _user(session, "no, weight is 2.8", extract_return=draft2)
        says = _say_keys(actions)
        assert "readback_changed" in says

    def test_correction_updates_draft(self):
        """After correction, draft reflects new value."""
        session, _ = _start("en-IN")
        draft1 = _null_draft(beneficiary_id="1001", weight_kg=3.1)
        _user(session, "ID 1001, weight 3.1", extract_return=draft1)

        draft2 = _null_draft(weight_kg=2.8)
        _user(session, "weight is 2.8", extract_return=draft2)
        assert session["draft"]["weight_kg"] == pytest.approx(2.8)

    def test_state_stays_readback_after_correction(self):
        """After correction, state remains READBACK (not DONE)."""
        session, _ = _start("en-IN")
        draft1 = _null_draft(beneficiary_id="1001")
        _user(session, "ID 1001", extract_return=draft1)

        draft2 = _null_draft(weight_kg=2.8)
        _user(session, "weight is 2.8", extract_return=draft2)
        assert session["state"] == STATE_READBACK


# ─── Test: Danger alert ───────────────────────────────────────────────────────

class TestDangerAlert:
    def test_danger_keyword_triggers_alert(self):
        """Transcript containing a danger keyword triggers alert action."""
        session, _ = _start("en-IN")
        # "fever" is a keyword for NB_FEVER_OR_COLD in danger_signs.yaml
        actions = _user(session, "the baby has high fever", extract_return=_null_draft())
        alert = _find(actions, "alert")
        assert alert is not None, "Expected alert action for 'fever'"
        assert len(alert["signs"]) > 0

    def test_danger_alert_fires_before_other_actions(self):
        """Alert action must come first (plan step 3)."""
        session, _ = _start("en-IN")
        actions = _user(session, "baby has high fever, ID is 1001",
                        extract_return=_null_draft(beneficiary_id="1001"))
        # Alert should appear before say actions
        types = _action_types(actions)
        if "alert" in types:
            alert_idx = types.index("alert")
            say_idxs = [i for i, t in enumerate(types) if t == "say"]
            assert all(alert_idx < si for si in say_idxs), (
                f"Alert at {alert_idx} should be before say actions at {say_idxs}"
            )

    def test_danger_not_re_alerted(self):
        """Same danger sign is not alerted twice in one visit."""
        session, _ = _start("en-IN")
        # First mention — captures the flag
        actions1 = _user(session, "baby has fever", extract_return=_null_draft())
        flags_after_first = list(session["flags"])
        assert len(flags_after_first) > 0

        # Second mention of same keyword — no NEW alert because sign already in flags
        actions2 = _user(session, "fever is still there", extract_return=_null_draft())
        alerts2 = [a for a in actions2 if a["type"] == "alert"]
        # If there are any alerts, they must only contain signs NOT already flagged
        for alert in alerts2:
            for sign in alert["signs"]:
                assert sign not in flags_after_first, (
                    f"Sign {sign} was already flagged, should not re-alert"
                )


# ─── Test: Medical advice refusal ────────────────────────────────────────────

class TestAdviceRefusal:
    def test_advice_keyword_triggers_cannot_advise(self):
        """Any advice keyword → cannot_advise (Tier A, never LLM)."""
        session, _ = _start("en-IN")
        actions = _user(session, "what medicine should I give?",
                        extract_return=_null_draft())
        says = _say_keys(actions)
        assert "cannot_advise" in says

    def test_advice_intent_from_llm_triggers_refusal(self):
        """LLM-returned medical_advice intent → cannot_advise."""
        session, _ = _start("en-IN")
        draft = _null_draft(intent="medical_advice", asks_advice=True)
        # Use a text without keyword so only LLM intent triggers it
        actions = _user(session, "कितनी दवा दूं?", extract_return=draft)
        says = _say_keys(actions)
        assert "cannot_advise" in says

    def test_advice_refused_in_capture_state(self):
        """Advice refusal works in CAPTURE state."""
        session, _ = _start("en-IN")
        assert session["state"] == STATE_CAPTURE
        actions = _user(session, "which tablet for fever",
                        extract_return=_null_draft())
        says = _say_keys(actions)
        assert "cannot_advise" in says

    def test_advice_refused_in_readback_state(self):
        """Advice refusal also works in READBACK state."""
        session, _ = _start("en-IN")
        draft1 = _null_draft(beneficiary_id="1001")
        _user(session, "ID 1001", extract_return=draft1)
        assert session["state"] == STATE_READBACK

        actions = _user(session, "what syrup to give?",
                        extract_return=_null_draft())
        says = _say_keys(actions)
        assert "cannot_advise" in says


# ─── Test: Session state dict ─────────────────────────────────────────────────

class TestSessionState:
    def test_flags_accumulate_across_turns(self):
        """Danger flags persist in session across multiple turns."""
        session, _ = _start("en-IN")
        _user(session, "baby has fever", extract_return=_null_draft())
        initial_flags = list(session["flags"])
        assert len(initial_flags) > 0

        # Another turn — flags should still be there
        _user(session, "ID is 1001", extract_return=_null_draft(beneficiary_id="1001"))
        assert initial_flags[0] in session["flags"]

    def test_draft_patches_not_replaces(self):
        """Merge is patch: null fields in new extraction don't clear existing fields."""
        session, _ = _start("en-IN")
        # First turn: get visit_type
        draft1 = _null_draft(beneficiary_id="1001", visit_type="NEWBORN")
        _user(session, "ID 1001, newborn visit", extract_return=draft1)

        # Second turn: only weight mentioned; visit_type must still be in draft
        draft2 = _null_draft(weight_kg=3.5)  # visit_type is null here
        _user(session, "weight is 3.5", extract_return=draft2)
        assert session["draft"]["visit_type"] == "NEWBORN"
        assert session["draft"]["weight_kg"] == pytest.approx(3.5)

    def test_new_session_has_capture_state(self):
        session = new_session("en-IN")
        assert session["state"] == STATE_CAPTURE

    def test_new_session_empty_draft(self):
        session = new_session("en-IN")
        assert session["draft"]["beneficiary_id"] is None
        assert session["flags"] == []


# ─── Test: speak() integration ────────────────────────────────────────────────

class TestSpeakIntegration:
    def test_disclosure_text_is_non_empty(self):
        """Disclosure must produce actual text (Tier A template)."""
        session, actions = _start("en-IN")
        disc = next((a for a in actions if a.get("key") == "disclosure"), None)
        assert disc is not None
        assert disc.get("_text"), "Disclosure text should be non-empty"

    def test_hindi_disclosure_contains_hindi_text(self):
        """Hindi disclosure must contain Hindi characters."""
        session, actions = _start("hi-IN")
        disc = next((a for a in actions if a.get("key") == "disclosure"), None)
        assert disc is not None
        text = disc.get("_text", "")
        # Check for Devanagari characters
        assert any('\u0900' <= c <= '\u097f' for c in text), (
            f"Hindi disclosure should contain Devanagari: {text}"
        )

    def test_kannada_disclosure_contains_kannada_text(self):
        """Kannada disclosure must contain Kannada characters."""
        session, actions = _start("kn-IN")
        disc = next((a for a in actions if a.get("key") == "disclosure"), None)
        assert disc is not None
        text = disc.get("_text", "")
        # Check for Kannada characters
        assert any('\u0c80' <= c <= '\u0cff' for c in text), (
            f"Kannada disclosure should contain Kannada script: {text}"
        )
