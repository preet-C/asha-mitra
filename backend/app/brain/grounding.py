# backend/app/brain/grounding.py
# A1 — Field grounding: how well can we verify each draft field against the transcript?
#
# WHY this file exists: Before asking the worker a question or reading back a value,
# we want to know whether that value was clearly heard in the transcript or just
# inferred by the LLM. Grounded = we can confirm it. Ungrounded = ask again.
#
# IMPORTANT: Grounding is session-only. It is NEVER saved to the database.
# A danger flag that is "ungrounded" still fires. Grounding only controls
# whether we ask the worker to repeat a field — it never suppresses an alert.
#
# Returns for each field:
#   "grounded"         - value confirmed in transcript by deterministic rule
#   "ambiguous"        - value present but incomplete (e.g. vaccine with missing dose)
#   "ungrounded"       - LLM produced a value but we cannot verify it in transcript
#   "validator_failed" - value failed a hard validation rule (e.g. ID not in repo)
#
# Contract: field_status(draft, transcript, beneficiary, lang) -> dict[str, str]
#   draft:       VisitDraft 4.1 (the current session draft)
#   transcript:  The raw STT text from this turn (or accumulated text)
#   beneficiary: The loaded beneficiary dict (from repo) or None
#   lang:        BCP-47 session language ("hi-IN", "kn-IN", "en-IN")
#
# Status values are deterministic — no probabilities, no scores.

import re
import pathlib
from datetime import date
from functools import lru_cache

import yaml

from app.brain.normalize import (
    parse_beneficiary_id,
    validate_weight_kg,
    resolve_next_visit,
    parse_spoken_number,
)
from app.brain.checks import check_visit_type

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def _load_vaccine_aliases() -> dict:
    """Load vaccine_aliases.yaml once and cache it.
    WHY cache: Called on every turn; file I/O would add latency."""
    path = _DATA_DIR / "vaccine_aliases.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def _load_number_tables() -> dict:
    """Load number_words.yaml once for transcript number matching."""
    path = _DATA_DIR / "number_words.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _normalize_transcript(text: str) -> str:
    """Lowercase and collapse whitespace for substring matching.
    WHY: STT output may have varied capitalisation and spacing."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _transcript_contains_number(transcript_norm: str, value: float, lang: str) -> bool:
    """Return True if the given numeric value appears in the normalised transcript.

    Checks three representations:
      1. Digit form: "2.8", "2800", "28", etc.
      2. English spoken words via num2words.
      3. Native word form from number_words.yaml (hi/kn).

    WHY: ASHA workers may say "do kilo aath sau" (Hindi) or "2.8 kilo"; we
    accept either. We use the existing normalize tables — no new data.
    """
    # 1. Digit form — check whole kg, grams, and decimal
    whole = int(value)
    grams = round((value - whole) * 1000)
    # Accept "2.8", "2800 gram", "2 kilo 800", individual digits etc.
    digit_candidates = [
        str(whole),
        str(round(value, 1)),
        str(grams) if grams else None,
    ]
    for dc in digit_candidates:
        if dc and dc in transcript_norm:
            return True

    # 2. Native number words from tables (hi / kn)
    tables = _load_number_tables()
    base_lang = lang.split("-")[0]
    if base_lang in ("hi", "kn"):
        num_map = tables.get(base_lang, {}).get("numbers", {})
        # Check if the whole-kg word appears in transcript
        kg_word = str(num_map.get(whole, "")).lower()
        if kg_word and len(kg_word) > 1 and kg_word in transcript_norm:
            return True
        # Check if the gram hundreds word appears
        if grams > 0:
            hundred_map = tables.get(base_lang, {}).get("hundreds", {})
            gram_hundred = round(grams / 100) * 100
            g_word = str(hundred_map.get(gram_hundred, "")).lower()
            if g_word and len(g_word) > 1 and g_word in transcript_norm:
                return True

    return False


def _transcript_has_date_clue(transcript_norm: str) -> bool:
    """Return True if the transcript contains any date/time indicator.

    Looks for: digit sequences, weekday words, month names (en/hi/kn).
    WHY: next_visit is grounded if the worker mentioned *some* temporal marker.
    We don't revalidate the date itself — resolve_next_visit already did that.
    """
    # Digit clue (a number in context of days/weeks/months)
    if re.search(r"\d", transcript_norm):
        return True

    # English weekday / time words
    en_time_words = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "week", "month", "day", "date", "next", "agle",
    ]
    for w in en_time_words:
        if w in transcript_norm:
            return True

    # Hindi time words (romanised + Devanagari)
    hi_time_words = [
        "hafte", "mahine", "din", "tarikh", "agle", "अगला", "हफ्ते", "महीने",
        "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार",
        "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "जून", "जुलाई", "अगस्त",
        "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
    ]
    for w in hi_time_words:
        if w in transcript_norm:
            return True

    # Kannada time words
    kn_time_words = [
        "vaarakke", "tingalige", "dina", "munde", "ಮುಂದೆ", "ವಾರ", "ತಿಂಗಳು",
        "ಸೋಮವಾರ", "ಮಂಗಳವಾರ", "ಬುಧವಾರ", "ಗುರುವಾರ", "ಶುಕ್ರವಾರ", "ಶನಿವಾರ", "ಭಾನುವಾರ",
        "ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್",
        "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್",
    ]
    for w in kn_time_words:
        if w in transcript_norm:
            return True

    return False


def _vaccine_alias_in_transcript(vaccine_id: str, transcript_norm: str) -> bool:
    """Return True if any alias for this vaccine ID appears in the transcript.

    WHY: Worker may say "penta one", "pentavalent 1", "dpt 1", etc. We check
    all aliases from vaccine_aliases.yaml across all three languages.
    Code-mixing means we cannot restrict to session language only.
    """
    aliases = _load_vaccine_aliases()
    vax_aliases = aliases.get(vaccine_id, {})
    for lang_code in ("en", "hi", "kn"):
        for alias in vax_aliases.get(lang_code, []):
            if alias.lower() in transcript_norm:
                return True
    return False


def _vaccine_needs_dose_number(vaccine_id: str) -> bool:
    """Return True if this vaccine has multiple doses so dose number matters.

    WHY: If a worker says "penta" without "one/two/three", we don't know
    which dose — the status is ambiguous. PENTA1 vs PENTA2 are different records.
    Single-dose vaccines (BCG, MR1) don't need this check.
    """
    # Vaccines that have multiple dose IDs in the schedule
    multi_dose_families = {
        "PENTA": ["PENTA1", "PENTA2", "PENTA3"],
        "OPV": ["OPV1", "OPV2", "OPV3"],
        "FIPV": ["FIPV1", "FIPV2", "FIPV3"],
        "RVV": ["RVV1", "RVV2", "RVV3"],
        "PCV": ["PCV1", "PCV2"],
        "MR": ["MR1", "MR2"],
        "VITA": ["VITA1", "VITA2"],
        "TD": ["TD1", "TD2"],
    }
    for family, members in multi_dose_families.items():
        if vaccine_id in members and len(members) > 1:
            return True
    return False


def _dose_number_in_transcript(vaccine_id: str, transcript_norm: str) -> bool:
    """Return True if the dose number for this vaccine appears in the transcript.

    WHY: "penta one" is grounded but "penta" alone is ambiguous for a multi-dose
    vaccine. We check the specific alias list which includes dose-numbered variants.
    If the specific alias for this vaccine ID matches, we know the dose is named.
    """
    # The specific alias for this vaccine ID already includes the dose number
    # (e.g. PENTA1 aliases include "penta one", "penta 1" but not bare "penta").
    # So if _vaccine_alias_in_transcript returns True, the dose IS mentioned.
    return _vaccine_alias_in_transcript(vaccine_id, transcript_norm)


def field_status(
    draft: dict,
    transcript: str,
    beneficiary: dict | None,
    lang: str,
) -> dict:
    """Return grounding status for each non-null field in the draft.

    Args:
        draft:       VisitDraft 4.1 (from session["draft"]).
        transcript:  Accumulated or current-turn raw STT text.
        beneficiary: Loaded beneficiary dict (session["beneficiary"]) or None.
        lang:        BCP-47 session language.

    Returns:
        dict[field_name -> status_string]
        Only non-null fields are included. Null fields stay null (not_mentioned).

    Status values:
        "grounded"         - confirmed in transcript by deterministic rule
        "ambiguous"        - value present but incomplete (dose number missing, etc.)
        "ungrounded"       - LLM produced value but cannot verify in transcript
        "validator_failed" - hard validation failure (ID not in repo, weight out of range)

    SAFETY: This function NEVER removes a symptom and NEVER suppresses a danger alert.
    Symptoms are assessed via scan_danger separately. Status here only affects
    whether the dialogue asks the worker to repeat a field.
    """
    result = {}
    transcript_norm = _normalize_transcript(transcript)
    today = date.today()

    # ── beneficiary_id ────────────────────────────────────────────────────────
    bid = draft.get("beneficiary_id")
    if bid is not None:
        # Hard rule: must be 4 digits AND must exist in repo
        if not re.fullmatch(r"\d{4}", str(bid)):
            result["beneficiary_id"] = "validator_failed"
        elif beneficiary is None:
            # get_beneficiary returned None → not found in repo
            result["beneficiary_id"] = "validator_failed"
        else:
            result["beneficiary_id"] = "grounded"

    # ── weight_kg ─────────────────────────────────────────────────────────────
    weight = draft.get("weight_kg")
    if weight is not None:
        # Validate range first
        kind = "mother" if draft.get("visit_type") in ("ANC", "PNC") else "child"
        validated = validate_weight_kg(float(weight), kind)
        if validated is None:
            result["weight_kg"] = "validator_failed"
        elif _transcript_contains_number(transcript_norm, float(weight), lang):
            result["weight_kg"] = "grounded"
        else:
            result["weight_kg"] = "ungrounded"

    # ── vaccines_given_today ──────────────────────────────────────────────────
    vaccines = draft.get("vaccines_given_today")
    if vaccines is not None:
        # Check each vaccine ID in the list
        any_ambiguous = False
        any_ungrounded = False
        for vax_id in vaccines:
            alias_found = _vaccine_alias_in_transcript(vax_id, transcript_norm)
            if not alias_found:
                any_ungrounded = True
            elif _vaccine_needs_dose_number(vax_id) and not _dose_number_in_transcript(vax_id, transcript_norm):
                # Alias matched but dose number unclear
                any_ambiguous = True
        # Worst status wins: ungrounded > ambiguous > grounded
        if any_ungrounded:
            result["vaccines_given_today"] = "ungrounded"
        elif any_ambiguous:
            result["vaccines_given_today"] = "ambiguous"
        else:
            result["vaccines_given_today"] = "grounded"

    # ── next_visit ────────────────────────────────────────────────────────────
    next_visit_spec = draft.get("next_visit")
    if next_visit_spec is not None:
        # First check the spec resolves to a future date
        resolved = resolve_next_visit(next_visit_spec, today)
        if resolved is None:
            result["next_visit"] = "validator_failed"
        elif _transcript_has_date_clue(transcript_norm):
            result["next_visit"] = "grounded"
        else:
            result["next_visit"] = "ungrounded"

    # ── visit_type ────────────────────────────────────────────────────────────
    vt = draft.get("visit_type")
    if vt is not None:
        # Reuse existing checks.check_visit_type for conflict detection.
        # WHY: If the visit type conflicts with beneficiary kind, it's validator_failed.
        ben_kind = beneficiary.get("kind") if beneficiary else None
        if check_visit_type(vt, ben_kind):
            # check_visit_type returns True = conflict detected
            result["visit_type"] = "validator_failed"
        else:
            result["visit_type"] = "grounded"

    # ── symptoms ──────────────────────────────────────────────────────────────
    symptoms = draft.get("symptoms")
    if symptoms is not None:
        # SAFETY RULE: Status NEVER removes a symptom and NEVER suppresses an alert.
        # scan_danger() runs independently of this. Here we only assess whether
        # the worker's quote was clearly in the transcript, for display purposes.
        sym_statuses = {}
        for sym in symptoms:
            sign_id = sym.get("sign_id")
            quote = sym.get("quote", "")
            status = sym.get("status")  # present / absent / unclear
            # Only check grounding for non-absent symptoms
            if status in ("present", "unclear") and quote:
                # Quote must be a substring of normalised transcript
                quote_norm = _normalize_transcript(quote)
                if quote_norm and quote_norm in transcript_norm:
                    sym_statuses[sign_id] = "grounded"
                else:
                    sym_statuses[sign_id] = "ungrounded"
            else:
                # absent or no quote → cannot verify, mark ungrounded
                sym_statuses[sign_id] = "ungrounded"

        # Roll up: if any symptom is ungrounded, the field is ungrounded
        # WHY: We want to surface the weakest link, but we NEVER suppress the alert.
        if any(s == "ungrounded" for s in sym_statuses.values()):
            result["symptoms"] = "ungrounded"
        else:
            result["symptoms"] = "grounded"

    return result
