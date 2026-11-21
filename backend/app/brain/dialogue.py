# backend/app/brain/dialogue.py
# P5a — Dialogue brain: state machine for the ASHA voice conversation.
#
# HOW THE STATE MACHINE WORKS (10 plain lines for beginners):
#  1. Worker presses button → "start" event → agent says disclosure + asks for ID.
#  2. Worker speaks → "user_text" event → extract fields from speech (P4).
#  3. EVERY turn: scan for danger signs (P3). If found → alert action immediately.
#  4. If medical advice asked → refuse (cannot_advise). Never answer. Never reach LLM.
#  5. While state=CAPTURE: merge new fields into draft. If ID missing → ask. If found → load beneficiary.
#  6. Once we have enough to read back → state=READBACK → say readback of 5 fields.
#  7. Worker says confirm word (haan/yes/sahi/ಸರಿ etc.) → save visit → state=DONE → say saved.
#  8. Worker says correction → extract_visit with existing draft → patch → readback_changed.
#  9. Unknown input after 2 tries → skip that field, move on.
# 10. All agent speech goes through speak() — never raw strings to TTS.
#
# Contract 4.3: handle(session, event) → list[dict]
#   event: {"type": "start"} | {"type": "user_text", "text": "..."}
#   returns: list of action dicts (say, alert, card, saved)

import logging
from datetime import date

from app.brain.extract import extract_visit
from app.brain.danger import scan_danger
from app.brain.normalize import resolve_next_visit
from app.brain.speak import speak, build_summary
from app.repo import memory_repo

log = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────────────────────────
# CAPTURE: collecting fields from worker speech
# READBACK: agent has read back 5 fields; waiting for confirm or correction
# DONE: visit saved

STATE_CAPTURE = "CAPTURE"
STATE_READBACK = "READBACK"
STATE_DONE = "DONE"

# ─── Confirm words per language (rule: only code decides, never LLM) ──────────
# Worker says one of these → save the visit.
_CONFIRM_WORDS = {
    "hi-IN": {"haan", "yes", "sahi", "theek hai", "correct", "ha", "han"},
    "kn-IN": {"ಸರಿ", "ಹೌದು", "yes", "correct", "sari", "howdu"},
    "en-IN": {"yes", "correct", "ok", "right", "yep", "yeah"},
}

# ─── Advice keywords — second safety layer (D14) ─────────────────────────────
# If ANY of these appear in transcript, refuse regardless of LLM intent label.
_ADVICE_KEYWORDS = {
    "medicine", "dawa", "dava", "dawai", "dose", "injection", "syrup",
    "treatment", "treat", "antibiotic", "paracetamol", "tablet",
    "कितनी दवा", "दवाई", "इलाज", "ಔಷಧಿ", "ಚಿಕಿತ್ಸೆ",
}

# ─── Fields required for read-back ───────────────────────────────────────────
# P5a reads back these 5 fields (plan step 6).
_READBACK_FIELDS = [
    "beneficiary_id", "visit_type", "weight_kg",
    "vaccines_given_today", "next_visit",
]


def new_session(lang: str = "en-IN") -> dict:
    """Create a fresh session dict for a new visit.

    Call this when the WebSocket connection opens (before the first "start" event).

    WHY a dict: simple, serialisable, easy to pass around between brain functions.
    Not a class — beginners find dicts easier to debug (just print it).
    """
    return {
        "lang": lang,          # BCP-47 language code
        "state": STATE_CAPTURE,
        "draft": _empty_draft(),
        "flags": [],           # danger sign IDs found so far this visit
        "asked": 0,            # number of questions asked (cap at 5, plan step 5)
        "beneficiary": None,   # loaded from repo once ID is confirmed
        "not_understood": 0,   # consecutive "I didn't understand" count
        "last_said_key": None, # for "repeat" intent
        "_last_variant": {},   # anti-repeat tracking for Tier B templates
    }


def handle(session: dict, event: dict) -> list[dict]:
    """Process one event and return a list of actions for the gateway.

    Args:
        session: Mutable session dict (from new_session). Brain updates it in place.
        event:   {"type": "start"} or {"type": "user_text", "text": "..."}

    Returns:
        List of action dicts. Gateway executes them in order:
          {"type": "say",   "key": "...", "vars": {...}}   → TTS
          {"type": "alert", "signs": [...]}                → danger banner + TTS
          {"type": "card",  "draft": {...}, "uncertain": []} → UI card update
          {"type": "saved", "visit_id": "..."}             → visit saved

    Never raises. Any unexpected error → say "system_error" and return.
    """
    try:
        return _handle(session, event)
    except Exception as exc:
        log.exception("Unexpected error in handle(): %s", exc)
        return [_say("system_error", {}, session)]


# ─── Internal dispatcher ──────────────────────────────────────────────────────

def _handle(session: dict, event: dict) -> list[dict]:
    etype = event.get("type")
    lang = session.get("lang", "en-IN")
    today = date.today()

    # ── start event ──
    if etype == "start":
        # Reset session language in case UI sent it here
        if "lang" in event:
            session["lang"] = event["lang"]
            lang = session["lang"]
        session["state"] = STATE_CAPTURE

        actions = []
        # Say disclosure first (Tier A — always template)
        actions.append(_say("disclosure", {}, session))

        # If ID not yet known, ask for it
        if not session["draft"].get("beneficiary_id"):
            actions.append(_say("ask_id", {}, session))
            session["last_said_key"] = "ask_id"

        return actions

    # ── user_text event ──
    if etype == "user_text":
        text = event.get("text", "").strip()
        if not text:
            return []

        actions = []

        # ── Step 1: Danger scan — runs EVERY turn, BEFORE anything else ──────
        # WHY first: Missed danger sign is worst possible failure.
        danger_actions = _check_danger(text, session, today)
        actions.extend(danger_actions)

        # ── Step 2: Medical advice check — two layers (D14) ──────────────────
        # Layer 1: keyword net (code)
        if _is_advice_request(text):
            actions.append(_say("cannot_advise", {}, session))
            # Repeat the last question so worker can continue
            if session.get("last_said_key"):
                actions.append(_say(session["last_said_key"], {}, session))
            return actions

        # ── Step 3: Handle by state ───────────────────────────────────────────
        if session["state"] == STATE_CAPTURE:
            actions.extend(_handle_capture(session, text, today))
        elif session["state"] == STATE_READBACK:
            actions.extend(_handle_readback(session, text, today))
        elif session["state"] == STATE_DONE:
            # Visit already saved — remind worker
            actions.append(_say("saved", _saved_vars(session), session))

        return actions

    log.warning("Unknown event type: %s", etype)
    return []


# ─── CAPTURE state ────────────────────────────────────────────────────────────

def _handle_capture(session: dict, text: str, today: date) -> list[dict]:
    """Extract fields from speech, merge into draft, ask for ID if missing,
    then read back once we have enough."""
    lang = session["lang"]
    actions = []

    # Extract from this turn's speech
    draft_new = extract_visit(text, lang, today, existing=session["draft"])

    # Merge: non-null new fields override old draft (patch semantics, plan step 2)
    _merge_draft(session["draft"], draft_new)

    # Check if LLM detected medical advice intent (layer 2 after keyword check)
    if draft_new.get("asks_advice") or draft_new.get("intent") == "medical_advice":
        actions.append(_say("cannot_advise", {}, session))
        if session.get("last_said_key"):
            actions.append(_say(session["last_said_key"], {}, session))
        return actions

    # Send card update so UI shows what we have so far
    actions.append({
        "type": "card",
        "draft": _safe_draft_for_ui(session["draft"], today),
        "uncertain": _uncertain_fields(session["draft"]),
    })

    # If ID just appeared, try to load beneficiary from repo
    if session["draft"].get("beneficiary_id") and not session["beneficiary"]:
        ben = memory_repo.get_beneficiary(session["draft"]["beneficiary_id"])
        if ben is None:
            # ID not found — ask worker to check
            actions.append(_say(
                "id_not_found",
                {"id": render_id_spoken(session["draft"]["beneficiary_id"], lang)},
                session,
            ))
            session["last_said_key"] = "id_not_found"
            # Clear the bad ID so worker can say a new one
            session["draft"]["beneficiary_id"] = None
            return actions
        # Beneficiary found — load into session
        session["beneficiary"] = ben
        log.info("Loaded beneficiary: %s (%s)", ben.get("name"), ben.get("id"))

    # If ID still missing, ask for it (once; not every turn)
    if not session["draft"].get("beneficiary_id"):
        if session.get("last_said_key") != "ask_id":
            actions.append(_say("ask_id", {}, session))
            session["last_said_key"] = "ask_id"
        return actions

    # Decide whether to go to READBACK
    # P5a: go to readback as soon as we have an ID (even if other fields are null)
    # WHY: worker can correct at readback; we don't want to interrogate too much.
    session["state"] = STATE_READBACK
    actions.extend(_do_readback(session, today))
    return actions


# ─── READBACK state ───────────────────────────────────────────────────────────

def _handle_readback(session: dict, text: str, today: date) -> list[dict]:
    """Worker is in confirm/correct mode. Check for confirm word or correction."""
    lang = session["lang"]
    actions = []

    text_lower = text.lower().strip()

    # Check if worker said a confirm word
    confirm_words = _CONFIRM_WORDS.get(lang, _CONFIRM_WORDS["en-IN"])
    # Also accept Devanagari/Kannada as-is; check substring for multi-word phrases
    is_confirm = any(
        cw in text_lower or cw in text  # handles "theek hai" substring + native script
        for cw in confirm_words
    )

    if is_confirm and not _looks_like_correction(text, lang):
        # Save the visit
        return _save_visit(session, text, today)

    # Not a confirm — treat as correction
    draft_new = extract_visit(text, lang, today, existing=session["draft"])

    # Check advice intent in correction speech too
    if draft_new.get("asks_advice") or draft_new.get("intent") == "medical_advice":
        actions.append(_say("cannot_advise", {}, session))
        actions.extend(_do_readback(session, today))
        return actions

    # Find which fields changed
    changed = _find_changed_fields(session["draft"], draft_new)

    if not changed:
        # Nothing changed — worker said something we didn't understand
        session["not_understood"] = session.get("not_understood", 0) + 1
        if session["not_understood"] >= 2:
            # After 2 misses, just save as-is
            return _save_visit(session, text, today)
        actions.append(_say("not_understood", {}, session))
        return actions

    # Reset not_understood counter when we understood something
    session["not_understood"] = 0

    # Merge changed fields into draft
    _merge_draft(session["draft"], draft_new)

    # Send card update
    actions.append({
        "type": "card",
        "draft": _safe_draft_for_ui(session["draft"], today),
        "uncertain": _uncertain_fields(session["draft"]),
    })

    # Say only what changed
    summary = _build_changed_summary(changed, session["draft"], session["flags"], lang, today)
    actions.append(_say("readback_changed", {"summary": summary}, session))
    session["last_said_key"] = "readback_changed"

    return actions


# ─── Save visit ───────────────────────────────────────────────────────────────

def _save_visit(session: dict, transcript: str, today: date) -> list[dict]:
    """Build final record, save it, return saved action."""
    draft = session["draft"]
    lang = session["lang"]

    # Resolve next_visit spec → ISO date
    next_visit_date = None
    if draft.get("next_visit"):
        nv = resolve_next_visit(draft["next_visit"], today)
        next_visit_date = nv.isoformat() if nv else None

    # Build final record (contract 4.2)
    record = {
        "beneficiary_id": draft.get("beneficiary_id"),
        "visit_type": draft.get("visit_type"),
        "visit_date": today.isoformat(),
        "weight_kg": draft.get("weight_kg"),
        "vaccines_given_today": draft.get("vaccines_given_today") or [],
        "vaccines_due": [],  # P3 vaccines_due computed on save (P5b adds this)
        "next_visit_date": next_visit_date,
        "danger_flags": session["flags"],
        "flagged": bool(session["flags"]),
    }

    visit_id = memory_repo.save_visit(record, transcript)
    session["state"] = STATE_DONE
    session["draft"]["_visit_id"] = visit_id  # store for later reference

    ben = session.get("beneficiary") or {}
    ben_id = draft.get("beneficiary_id") or ""
    ben_name = ben.get("name", "")

    return [
        {
            "type": "saved",
            "visit_id": visit_id,
        },
        _say("saved", {"id": ben_id, "name": ben_name}, session),
    ]


# ─── Readback helpers ─────────────────────────────────────────────────────────

def _do_readback(session: dict, today: date) -> list[dict]:
    """Build and return readback action (say readback + card)."""
    lang = session["lang"]
    summary = build_summary(session["draft"], session["flags"], lang, today)
    action = _say("readback", {"summary": summary}, session)
    session["last_said_key"] = "readback"
    return [action]


def _build_changed_summary(
    changed_fields: list[str],
    draft: dict,
    flags: list[str],
    lang: str,
    today: date,
) -> str:
    """Build a short summary string covering only the changed fields.

    WHY: readback_changed says "Changed. <only what changed>. Is that correct?"
    Reading back ALL 5 fields again on every correction is tedious.
    """
    # Build a partial draft with only changed fields
    partial = {f: draft.get(f) for f in changed_fields}
    # Always include ID for context
    partial["beneficiary_id"] = draft.get("beneficiary_id")
    return build_summary(partial, [], lang, today)


# ─── Danger check ─────────────────────────────────────────────────────────────

def _check_danger(text: str, session: dict, today: date) -> list[dict]:
    """Run P3 danger scan. If new signs found, emit alert action.

    WHY every turn: worker may mention signs in any part of the conversation.
    WHY before read-back: alert fires immediately, even mid-sentence (plan step 3).
    """
    lang = session.get("lang", "en-IN")
    ben = session.get("beneficiary")

    # beneficiary_kind tells scan_danger which applies_to filter to use.
    # We pass None if unknown so it scans ALL signs (safe, never restricts).
    ben_kind = ben.get("kind", "").upper() if ben else None
    # Map repo kind ("child"/"mother") → danger applies_to ("NEWBORN"/"MOTHER")
    # WHY: danger_signs.yaml uses NEWBORN/MOTHER; synthetic_beneficiaries uses child/mother.
    kind_map = {"child": "NEWBORN", "mother": "MOTHER"}
    applies_kind = kind_map.get(ben_kind.lower() if ben_kind else "", None)

    # scan_danger returns {"alert": [{id, trigger}...], "confirm_absent": [...]}
    result = scan_danger(text, symptoms=None, beneficiary_kind=applies_kind, lang=lang)
    alert_signs = result.get("alert", [])

    # Extract just the sign IDs from alert list
    new_sign_ids = [s["id"] for s in alert_signs]

    # Add only truly novel signs (don't re-alert same sign twice this visit)
    novel = [sid for sid in new_sign_ids if sid not in session["flags"]]
    if not novel:
        return []

    session["flags"].extend(novel)
    # Return one alert action with all novel sign IDs
    return [{"type": "alert", "signs": novel}]


# ─── Advice check ─────────────────────────────────────────────────────────────

def _is_advice_request(text: str) -> bool:
    """Check if transcript contains any advice keyword (layer 1 of D14).

    WHY keyword net: LLM intent is layer 2. Code-level keyword match runs even
    if the LLM call is slow or down — safety must not depend on LLM availability.
    """
    text_lower = text.lower()
    return any(kw in text_lower for kw in _ADVICE_KEYWORDS)


# ─── Draft helpers ────────────────────────────────────────────────────────────

def _empty_draft() -> dict:
    """Return a VisitDraft with all fields null (not_mentioned)."""
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


def _merge_draft(existing: dict, new: dict) -> None:
    """Merge non-null fields from new into existing (patch semantics, plan step 2).

    WHY patch, not replace: Worker says "actually weight is 2.8" — only weight
    should change. All other already-captured fields must stay.
    """
    for field, val in new.items():
        if field.startswith("_"):
            continue  # skip internal keys like _fallback
        if val is not None:
            existing[field] = val


def _find_changed_fields(old: dict, new: dict) -> list[str]:
    """Return list of field names that differ between old and new (non-null in new)."""
    changed = []
    for field, val in new.items():
        if field.startswith("_") or val is None:
            continue
        if old.get(field) != val:
            changed.append(field)
    return changed


def _uncertain_fields(draft: dict) -> list[str]:
    """Return list of fields that are still null — shown yellow in UI card."""
    important = ["beneficiary_id", "visit_type", "weight_kg", "next_visit"]
    return [f for f in important if draft.get(f) is None]


def _safe_draft_for_ui(draft: dict, today: date) -> dict:
    """Convert draft to a UI-safe dict (resolve next_visit spec → ISO date string).

    WHY: UI card expects a date string for next_visit_date, not the spec dict.
    """
    out = {k: v for k, v in draft.items() if not k.startswith("_")}
    # Resolve next_visit spec to date string for display
    if out.get("next_visit"):
        nv = resolve_next_visit(out["next_visit"], today)
        out["next_visit_date"] = nv.isoformat() if nv else None
    else:
        out["next_visit_date"] = None
    return out


def _looks_like_correction(text: str, lang: str) -> bool:
    """Heuristic: does this text look like a correction rather than pure confirm?

    If worker says "haan, weight is 2.8" we should treat it as correction+confirm.
    WHY: Some workers add corrections even while confirming. We re-extract to catch
    any new field values, then save.
    """
    # Simple heuristic: contains a digit or unit word → probably has data in it
    import re
    return bool(re.search(r"\d", text))


# ─── speak() shortcut ─────────────────────────────────────────────────────────

def _say(key: str, vars: dict, session: dict) -> dict:
    """Create a "say" action dict. Gateway calls speak() to get final text.

    WHY return action dict, not text: Gateway owns TTS. Brain returns structured
    actions. This keeps brain transport-agnostic (contract 4.3).
    """
    # We also pre-compute the text here so cli_demo.py can print it without
    # duplicating the speak() call.
    action = {"type": "say", "key": key, "vars": vars}
    action["_text"] = speak(action, session)  # pre-rendered for CLI / tests
    return action


def _say_key_to_session(key: str, session: dict) -> None:
    """Record the last spoken template key so "repeat" intent can replay it."""
    session["last_said_key"] = key


# ─── Render ID spoken ─────────────────────────────────────────────────────────

def render_id_spoken(id_str: str, lang: str) -> str:
    """Return digit-by-digit spoken form of ID for use in vars dicts.
    WHY: id_not_found template uses {id} as a spoken string, not digits."""
    from app.brain.normalize import render_number
    return render_number(lang, "id", str(id_str))


# ─── Saved vars ───────────────────────────────────────────────────────────────

def _saved_vars(session: dict) -> dict:
    """Build vars dict for the "saved" template."""
    ben = session.get("beneficiary") or {}
    return {
        "id": session["draft"].get("beneficiary_id", ""),
        "name": ben.get("name", ""),
    }
