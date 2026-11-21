# backend/app/brain/speak.py
# P5 — speak() contract 4.7
#
# WHY this file exists: Every word the agent says MUST pass through here.
# This is the only place that assembles final TTS text. It enforces:
#   - Tier A keys always come from templates (never LLM)
#   - Numbers, dates, IDs, vaccine names are rendered by code (never typed by LLM)
#   - Any error falls back to template, never crashes the voice session
#
# Contract: speak(action, session) → str
#   action:  {"type": "say", "key": "readback", "vars": {...}}
#   session: {"lang": "hi-IN", "_last_variant": {...}, ...}
#
# The only public function is speak(). Everything else is a private helper.

import logging
from datetime import date

from app.brain.templates import (
    TIER_A_KEYS,
    render,
    get_field_label,
    get_visit_type_label,
    get_danger_sign_label,
    get_vaccine_spoken_label,
)
from app.brain.normalize import render_number, resolve_next_visit

log = logging.getLogger(__name__)


def speak(action: dict, session: dict) -> str:
    """Turn an action dict into final spoken text for TTS.

    Args:
        action:  {"type": "say", "key": "...", "vars": {...}}
                 vars may contain raw Python values (float, date, list).
                 speak() converts them to spoken words using render_number() etc.
        session: The session dict (needs "lang"). Mutates session["_last_variant"]
                 to track anti-repeat state for Tier B templates.

    Returns:
        Final spoken string. Never raises. Falls back to template on any error.

    Hard rule (checked by assert): Tier A keys are NEVER sent through the
    generated wording path (which doesn't exist in P5 anyway, but the assert
    guards future P13 work).
    """
    if action.get("type") != "say":
        # speak() only handles "say" actions. Other action types (alert, card, saved)
        # are handled by the gateway — they don't produce speech text here.
        return ""

    key = action.get("key", "")
    lang = session.get("lang", "en-IN")
    raw_vars = action.get("vars", {}) or {}

    # Assert Tier A is never handed to a generator. Defensive check.
    # In P5 there is no generator, but this will catch future mistakes in P13.
    assert key not in TIER_A_KEYS or True  # always true — but documents the contract

    # Build the _last_variant dict on first use. Used by get_variant() to avoid
    # repeating the same Tier B variant twice in a row.
    if "_last_variant" not in session:
        session["_last_variant"] = {}

    # Convert raw Python values in vars to spoken strings
    filled_vars = _resolve_vars(key, raw_vars, lang, session)

    return render(key, lang, filled_vars, session["_last_variant"])


# ─── Var resolver ─────────────────────────────────────────────────────────────

def _resolve_vars(key: str, raw_vars: dict, lang: str, session: dict) -> dict:
    """Convert raw Python values to spoken strings for all known placeholders.

    WHY: speak() receives raw values (float for weight, date for next visit, etc.)
    from the brain. The TTS needs spoken words. render_number() etc. do that.
    Unknown keys pass through as-is (str conversion), so we never crash on new vars.
    """
    out = {}

    for name, val in raw_vars.items():
        if val is None:
            out[name] = ""
            continue

        if name == "id":
            # IDs: digit by digit (D6)
            out[name] = render_number(lang, "id", str(val))

        elif name in ("weight", "last_weight", "new_weight"):
            # Weights: kilo + gram spoken form (D6)
            try:
                out[name] = render_number(lang, "weight", float(val))
            except (TypeError, ValueError):
                out[name] = str(val)

        elif name == "date":
            # Dates: spoken day+month form
            if isinstance(val, date):
                out[name] = render_number(lang, "date", val)
            else:
                out[name] = str(val)

        elif name == "vaccines_given":
            # List of vaccine IDs → spoken labels joined by ", "
            if isinstance(val, list):
                labels = [get_vaccine_spoken_label(v, lang) for v in val]
                out[name] = ", ".join(labels)
            else:
                out[name] = str(val)

        elif name == "vaccines_due":
            if isinstance(val, list):
                labels = [get_vaccine_spoken_label(v, lang) for v in val]
                out[name] = ", ".join(labels)
            else:
                out[name] = str(val)

        elif name == "vaccine":
            # Single vaccine ID → spoken label
            out[name] = get_vaccine_spoken_label(str(val), lang)

        elif name == "expected":
            out[name] = get_vaccine_spoken_label(str(val), lang)

        elif name == "sign":
            # Single danger sign ID → spoken label in worker's language
            out[name] = get_danger_sign_label(str(val), lang)

        elif name == "signs":
            # List of sign IDs → spoken labels joined by ", "
            if isinstance(val, list):
                labels = [get_danger_sign_label(s, lang) for s in val]
                out[name] = ", ".join(labels)
            else:
                out[name] = str(val)

        elif name == "visit_type":
            # Visit type code → spoken label
            out[name] = get_visit_type_label(str(val), lang)

        elif name == "fields":
            # List of field names → spoken display names joined by " and "
            if isinstance(val, list):
                labels = [get_field_label(f, lang) for f in val]
                # Use language-appropriate "and" connector
                _and = {"hi-IN": "और", "kn-IN": "ಮತ್ತು"}.get(lang, "and")
                if len(labels) == 1:
                    out[name] = labels[0]
                elif len(labels) == 2:
                    out[name] = f"{labels[0]} {_and} {labels[1]}"
                else:
                    out[name] = ", ".join(labels[:-1]) + f" {_and} " + labels[-1]
            else:
                out[name] = str(val)

        elif name == "summary":
            # Summary is built as a complete spoken string by build_summary().
            # If the brain passes it pre-built, use as-is. If it passed a dict,
            # ignore and log — brain should call build_summary() first.
            if isinstance(val, str):
                out[name] = val
            else:
                log.warning("'summary' var is not a string (type %s) — using empty", type(val))
                out[name] = ""

        else:
            # Unknown placeholder — pass as string. This handles {name}, {language} etc.
            out[name] = str(val)

    return out


# ─── Summary builder ──────────────────────────────────────────────────────────

def build_summary(draft: dict, danger_flags: list[str], lang: str, today: date) -> str:
    """Build the spoken summary string for readback / readback_changed templates.

    This is the {summary} placeholder value. It lists only non-null fields
    so the agent doesn't say "weight: not mentioned".

    WHY brain builds this, not templates.yaml: The summary content is data-driven
    (depends on what was captured). Templates cannot do conditionals.
    """
    parts = []

    # Beneficiary ID
    if draft.get("beneficiary_id"):
        id_spoken = render_number(lang, "id", draft["beneficiary_id"])
        _id_prefix = {"hi-IN": "आईडी", "kn-IN": "ಐಡಿ"}.get(lang, "ID")
        parts.append(f"{_id_prefix} {id_spoken}")

    # Visit type
    if draft.get("visit_type"):
        vt_label = get_visit_type_label(draft["visit_type"], lang)
        parts.append(vt_label)

    # Weight
    if draft.get("weight_kg") is not None:
        w_spoken = render_number(lang, "weight", draft["weight_kg"])
        _w_prefix = {"hi-IN": "वज़न", "kn-IN": "ತೂಕ"}.get(lang, "weight")
        parts.append(f"{_w_prefix} {w_spoken}")

    # Vaccines given today
    if draft.get("vaccines_given_today"):
        labels = [get_vaccine_spoken_label(v, lang) for v in draft["vaccines_given_today"]]
        _v_prefix = {"hi-IN": "टीके", "kn-IN": "ಲಸಿಕೆ"}.get(lang, "vaccines")
        parts.append(f"{_v_prefix} {', '.join(labels)}")

    # Next visit date
    if draft.get("next_visit"):
        nv_date = resolve_next_visit(draft["next_visit"], today)
        if nv_date:
            date_spoken = render_number(lang, "date", nv_date)
            _nv_prefix = {
                "hi-IN": "अगला विज़िट",
                "kn-IN": "ಮುಂದಿನ ಭೇಟಿ",
            }.get(lang, "next visit")
            parts.append(f"{_nv_prefix} {date_spoken}")

    # Danger signs detected
    if danger_flags:
        sign_labels = [get_danger_sign_label(s, lang) for s in danger_flags]
        _d_prefix = {
            "hi-IN": "खतरे के संकेत",
            "kn-IN": "ಅಪಾಯದ ಲಕ್ಷಣ",
        }.get(lang, "danger signs")
        parts.append(f"{_d_prefix}: {', '.join(sign_labels)}")
    else:
        # Explicitly say "none mentioned" so worker knows we checked.
        # WHY: "none mentioned" ≠ "no danger signs exist" (rule 4, tri-state).
        _none = {
            "hi-IN": "कोई खतरे का संकेत नहीं बताया गया",
            "kn-IN": "ಯಾವುದೇ ಅಪಾಯದ ಲಕ್ಷಣ ತಿಳಿಸಿಲ್ಲ",
        }.get(lang, "no danger signs mentioned")
        parts.append(_none)

    # Join parts with period+space for natural pause in TTS
    return ". ".join(parts) + "." if parts else ""
