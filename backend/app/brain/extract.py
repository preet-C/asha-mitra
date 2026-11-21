# backend/app/brain/extract.py
# P4 — Visit extraction
#
# WHY this file exists: The ASHA worker speaks free-form notes in Hindi, Kannada,
# or English (code-mixed). This module turns that raw transcript into a structured
# VisitDraft (contract 4.1) the dialogue brain can act on.
#
# Flow: LLM parse → shape validate → P2 normalise → fallback if LLM fails twice.
#
# Contract: extract_visit(text, lang, today, existing=None) -> dict (VisitDraft 4.1)

import json
import logging
import pathlib
from datetime import date
from typing import Optional

import yaml

from app.brain.llm import llm_json
from app.brain.normalize import (
    parse_beneficiary_id,
    validate_weight_kg,
    parse_weight_fallback,
)

log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"

# ─── Closed lists (loaded once from data files) ───────────────────────────────

# WHY load from data files: If we add a new danger sign to danger_signs.yaml,
# the closed list in the prompt updates automatically. No code change needed.

_VISIT_TYPES = {"ANC", "PNC", "NEWBORN", "IMMUNISATION", "OTHER"}

_SYMPTOM_STATUSES = {"present", "absent", "unclear"}

_INTENT_LABELS = {
    "notes", "confirm", "deny_or_correct", "repeat", "slower",
    "skip_field", "later", "start_over", "switch_language",
    "medical_advice", "who_are_you", "what_can_you_do", "how_to_use", "off_topic",
}


def _load_sign_ids() -> set:
    """Load sign IDs from danger_signs.yaml."""
    path = _DATA_DIR / "danger_signs.yaml"
    signs = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {s["id"] for s in signs}


def _load_vaccine_ids() -> set:
    """Load all vaccine IDs from vaccine_schedule.json."""
    path = _DATA_DIR / "vaccine_schedule.json"
    sched = json.loads(path.read_text(encoding="utf-8"))
    ids = {v["id"] for v in sched.get("child", [])}
    ids |= {v["id"] for v in sched.get("mother", [])}
    return ids


# Load at module import time (once). These don't change during a session.
_SIGN_IDS = _load_sign_ids()
_VACCINE_IDS = _load_vaccine_ids()


# ─── System prompt builder ────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    """
    Load extract_v1.txt and inject the closed lists from data files.

    WHY inject at runtime: Closed lists come from YAML/JSON data files,
    not hardcoded in the prompt. Adding a new vaccine ID to vaccine_schedule.json
    automatically makes the prompt aware of it.
    """
    template = (_PROMPTS_DIR / "extract_v1.txt").read_text(encoding="utf-8")

    sign_list = "\n".join(f"  {s}" for s in sorted(_SIGN_IDS))
    vaccine_list = "\n".join(f"  {v}" for v in sorted(_VACCINE_IDS))
    visit_type_list = " | ".join(sorted(_VISIT_TYPES))
    intent_list = " | ".join(sorted(_INTENT_LABELS))

    return template.format(
        sign_ids=sign_list,
        vaccine_ids=vaccine_list,
        visit_types=visit_type_list,
        intent_labels=intent_list,
    )


# ─── Main extraction function ─────────────────────────────────────────────────

def extract_visit(
    text: str,
    lang: str,
    today: date,
    existing: Optional[dict] = None,
) -> dict:
    """
    Turn a raw speech transcript into a VisitDraft (contract 4.1).

    Args:
        text:     Raw transcript from STT (Devanagari / Kannada script / Latin,
                  codemix format from Gnani Prisma v3).
        lang:     BCP-47 language code: 'hi-IN', 'kn-IN', or 'en-IN'.
        today:    Today's date — passed in so tests can freeze time easily.
        existing: Current draft when worker is correcting a field.
                  Non-null LLM fields from this call override existing fields
                  (patch semantics — only what's said this turn changes).

    Returns:
        dict matching VisitDraft 4.1. Fields not mentioned = null.
        Contains '_fallback': True if LLM failed and regex was used instead.

    Never raises — demo must not crash.
    """
    system_prompt = _build_system_prompt()

    # Build the user message. When correcting, give LLM context of what was
    # already captured so it understands what the worker is changing.
    if existing:
        user_msg = (
            f"Language: {lang}\n"
            f"Today: {today.isoformat()}\n"
            f"Current draft (worker is correcting this):\n"
            f"{json.dumps(existing, ensure_ascii=False)}\n"
            f"Worker speech: {text}"
        )
    else:
        user_msg = (
            f"Language: {lang}\n"
            f"Today: {today.isoformat()}\n"
            f"Worker speech: {text}"
        )

    # Attempt LLM. llm_json() already retries once on network errors.
    # We try the full call twice at this level to handle parse failures
    # that survive llm_json's internal retry (e.g. structurally wrong JSON).
    raw = None
    for attempt in range(2):
        try:
            raw = llm_json(system_prompt, user_msg)
            break  # success — exit retry loop
        except ValueError as e:
            log.warning("extract_visit attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                # Both attempts failed — fall back to regex helpers from P2
                log.error(
                    "LLM failed twice. Falling back to regex extraction. "
                    "Danger keyword scan (P3) still runs on raw transcript."
                )
                return _fallback_draft(text)

    if raw is None:
        return _fallback_draft(text)

    return _validate_and_clean(raw, today)


# ─── Shape validation ─────────────────────────────────────────────────────────

def _validate_and_clean(raw: dict, today: date) -> dict:
    """
    Validate and clean the LLM output dict.

    WHY validate: LLM can hallucinate field values or return wrong enum values.
    Rule: unknown enum → null (safe default). Never crash on bad LLM output.
    """
    out = {}

    # beneficiary_id — run through P2 parser (handles digit words, spaced digits)
    raw_id = raw.get("beneficiary_id")
    if raw_id is not None:
        # parse_beneficiary_id returns None if not exactly 4 digits
        out["beneficiary_id"] = parse_beneficiary_id(str(raw_id))
    else:
        out["beneficiary_id"] = None

    # visit_type — must be in closed list, else null
    vt = raw.get("visit_type")
    out["visit_type"] = vt if vt in _VISIT_TYPES else None

    # weight_kg — validate range via P2 (child 1–25 kg, mother 30–120 kg)
    raw_weight = raw.get("weight_kg")
    if raw_weight is not None:
        try:
            w = float(raw_weight)
            # Choose weight kind from visit type. Unknown → assume child (tighter range).
            kind = "mother" if out.get("visit_type") in ("ANC", "PNC") else "child"
            out["weight_kg"] = validate_weight_kg(w, kind)  # None if out of range
        except (TypeError, ValueError):
            out["weight_kg"] = None
    else:
        out["weight_kg"] = None

    # vaccines_given_today — filter to known IDs, null if none survive
    given = raw.get("vaccines_given_today")
    if isinstance(given, list):
        known = [v for v in given if v in _VACCINE_IDS]
        out["vaccines_given_today"] = known if known else None
    else:
        out["vaccines_given_today"] = None

    # vaccines_due_stated — same filtering
    due = raw.get("vaccines_due_stated")
    if isinstance(due, list):
        known = [v for v in due if v in _VACCINE_IDS]
        out["vaccines_due_stated"] = known if known else None
    else:
        out["vaccines_due_stated"] = None

    # next_visit — validate structure (P5 calls resolve_next_visit() to get the date)
    out["next_visit"] = _validate_next_visit(raw.get("next_visit"))

    # symptoms — validate sign IDs and statuses. Empty list → null (not_mentioned).
    syms = raw.get("symptoms")
    if isinstance(syms, list) and syms:
        cleaned = []
        for s in syms:
            if not isinstance(s, dict):
                continue
            sid = s.get("sign_id")
            status = s.get("status")
            if sid in _SIGN_IDS and status in _SYMPTOM_STATUSES:
                cleaned.append({
                    "sign_id": sid,
                    "status": status,
                    # quote is optional — cap length to avoid runaway strings
                    "quote": str(s.get("quote", ""))[:300],
                })
        out["symptoms"] = cleaned if cleaned else None
    else:
        # Normalize [] → null. WHY: null means "not mentioned".
        # An empty list would wrongly imply "worker said there are no symptoms".
        out["symptoms"] = None

    # asks_advice — boolean. Default False is safe: P5 keyword net is second layer.
    out["asks_advice"] = bool(raw.get("asks_advice", False))

    # intent — must be a known label; unknown → "notes" (safe default)
    intent = raw.get("intent", "notes")
    out["intent"] = intent if intent in _INTENT_LABELS else "notes"

    return out


def _validate_next_visit(nv) -> Optional[dict]:
    """
    Validate the next_visit spec returned by the LLM.

    Contract 4.1 defines three kinds: relative_days, weekday, absolute.
    Malformed specs → null (not_mentioned). P5 calls resolve_next_visit()
    from normalize.py to convert the spec into an actual ISO date.
    """
    if not isinstance(nv, dict):
        return None

    kind = nv.get("kind")

    if kind == "relative_days":
        try:
            n = int(nv["n"])
            return {"kind": "relative_days", "n": n} if n > 0 else None
        except (KeyError, TypeError, ValueError):
            return None

    elif kind == "weekday":
        weekday = nv.get("weekday")
        which = nv.get("which", "next")
        if weekday and which in ("this", "next"):
            return {"kind": "weekday", "weekday": str(weekday), "which": which}
        return None

    elif kind == "absolute":
        try:
            day = int(nv["day"])
            month = int(nv["month"])
            year = nv.get("year")  # may be null per contract 4.1
            if 1 <= day <= 31 and 1 <= month <= 12:
                return {
                    "kind": "absolute",
                    "day": day,
                    "month": month,
                    "year": int(year) if year else None,
                }
        except (KeyError, TypeError, ValueError):
            pass
        return None

    return None  # unknown kind


# ─── Regex fallback ───────────────────────────────────────────────────────────

def _fallback_draft(text: str) -> dict:
    """
    Emergency fallback when LLM fails twice.

    WHY: The demo must never crash. P2 regex helpers salvage what they can.

    Shape: Valid VisitDraft 4.1. All fields not_mentioned (null) except
    beneficiary_id and weight_kg which regex can often extract.

    Safety notes:
    - asks_advice=False is safe: P5 keyword net is a second independent layer.
    - symptoms=null: P3 keyword scan STILL runs on raw transcript, so danger
      detection is degraded (LLM status check can't run) but NOT blind.
    - '_fallback' key signals P5 that LLM was unavailable this turn.
    """
    return {
        "beneficiary_id": parse_beneficiary_id(text),
        "visit_type": None,
        "weight_kg": parse_weight_fallback(text),
        "vaccines_given_today": None,
        "vaccines_due_stated": None,
        "next_visit": None,
        "symptoms": None,
        "asks_advice": False,
        "intent": "notes",
        "_fallback": True,  # internal signal for P5 — not part of public contract 4.1
    }
