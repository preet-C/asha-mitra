# backend/app/brain/danger.py
# P3 — Danger sign scanner
# WHY: Missing a danger sign is the worst possible failure — it harms a real patient.
#      This module runs deterministic keyword + LLM-status rules. No LLM calls here.
#      It fires EVERY turn, BEFORE read-back (contract 4.3).

import re
import pathlib
from functools import lru_cache

import yaml

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def _load_signs() -> list[dict]:
    """Load danger_signs.yaml once and cache it.
    WHY: File I/O on every call would slow down per-turn scanning."""
    path = _DATA_DIR / "danger_signs.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _keyword_hit(transcript: str, sign: dict) -> bool:
    """Return True if any keyword for this sign appears in the transcript.

    WHY (from review): We scan ALL three language keyword lists (en/hi/kn) on
    every transcript, regardless of session language. ASHA workers code-mix freely
    — a Hindi-session worker might say a Kannada or English word. Missing it because
    we only checked one language's list could mean a missed danger sign.

    Matching rule: case-insensitive substring match. Short keywords (<=3 chars) are
    matched as whole words only, to reduce false positives (e.g. "hot" in "photo").
    """
    if not transcript:
        return False

    text_lower = transcript.lower()
    kw_block = sign.get("keywords", {})

    for lang_code in ("en", "hi", "kn"):
        for kw in kw_block.get(lang_code, []):
            kw_lower = kw.lower()
            if len(kw_lower) <= 3:
                # Whole-word match for short keywords to avoid false positives
                pattern = r"(?<!\w)" + re.escape(kw_lower) + r"(?!\w)"
                if re.search(pattern, text_lower):
                    return True
            else:
                if kw_lower in text_lower:
                    return True

    return False


def _get_llm_status(sign_id: str, symptoms: list[dict] | None) -> str | None:
    """Find the LLM-extracted status for a given sign_id from the symptoms list.

    Returns "present" | "absent" | "unclear" | None (not mentioned by LLM).
    WHY: LLM status and keyword net are two independent detection layers (D4).
    """
    if not symptoms:
        return None
    for s in symptoms:
        if s.get("sign_id") == sign_id:
            return s.get("status")  # "present" | "absent" | "unclear" | None
    return None


def scan_danger(
    transcript: str,
    symptoms: list[dict] | None,
    beneficiary_kind: str | None,
    lang: str,
) -> dict:
    """Scan transcript + LLM symptoms for danger signs. Run every turn.

    Args:
        transcript:       Raw STT text from worker this turn.
        symptoms:         List of {sign_id, status, quote} from LLM extraction.
                          May be None or [] if LLM failed.
        beneficiary_kind: "NEWBORN" | "MOTHER" | None.
                          None → scan all signs (safe, never restricts).
        lang:             Session language e.g. "hi-IN". Reserved for future use
                          (we scan all keyword lists regardless — see WHY above).

    Returns:
        {
            "alert": [
                {"id": "NB_FEVER_OR_COLD", "trigger": "llm|keyword|both"}
            ],
            "confirm_absent": [
                {"id": "MO_BLEEDING", "trigger": "keyword"}
            ]
        }

    Rules (recall-first — a missed sign is the worst failure):
      1. LLM status "present" or "unclear" → alert immediately.
      2. Keyword hit in transcript AND LLM did NOT say "absent" → alert.
      3. Keyword hit AND LLM explicitly said "absent" → confirm_absent.
         (Do NOT silently drop. "bleeding nahi ruk raha" = still bleeding.)
      4. Restrict by applies_to if beneficiary_kind is known.
      5. Each sign fires at most once per call (deduplicated).
    """
    signs = _load_signs()
    alert: dict[str, dict] = {}     # sign_id → {"id": ..., "trigger": ...}
    confirm: dict[str, dict] = {}   # sign_id → {"id": ..., "trigger": ...}

    for sign in signs:
        sign_id = sign["id"]
        applies_to = sign.get("applies_to", "BOTH")

        # Rule 4: skip if sign doesn't apply to this beneficiary kind
        if beneficiary_kind and applies_to != "BOTH":
            if applies_to != beneficiary_kind.upper():
                continue

        llm_status = _get_llm_status(sign_id, symptoms)
        kw_hit = _keyword_hit(transcript, sign)

        # Rule 1: LLM says present or unclear → alert
        if llm_status in ("present", "unclear"):
            if kw_hit:
                trigger = "both"
            else:
                trigger = "llm"
            alert[sign_id] = {"id": sign_id, "trigger": trigger}
            continue

        # Rule 2 & 3: keyword hit
        if kw_hit:
            if llm_status == "absent":
                # Rule 3: keyword + LLM absent → needs confirmation (may be negation error)
                confirm[sign_id] = {"id": sign_id, "trigger": "keyword"}
            else:
                # Rule 2: keyword hit, LLM silent → alert (safe side)
                alert[sign_id] = {"id": sign_id, "trigger": "keyword"}

    return {
        "alert": list(alert.values()),
        "confirm_absent": list(confirm.values()),
    }
