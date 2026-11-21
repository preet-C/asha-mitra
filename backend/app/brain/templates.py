# backend/app/brain/templates.py
# P5 — Template loader + placeholder renderer.
#
# WHY this file exists: All agent speech comes from templates.yaml (not raw strings
# in code). This module loads the YAML once and provides two things:
#   1. get_variant(key, lang) → one string (randomly chosen variant for Tier B)
#   2. render(key, lang, vars) → filled string ready for TTS
#
# Hard rule: Tier A keys (disclosure, refer_phc, cannot_advise, readback,
#            readback_changed, saved) are ALWAYS served from template.
#            Code asserts this. Never from LLM.

import pathlib
import random
import logging
import re
from functools import lru_cache

import yaml

log = logging.getLogger(__name__)

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

# Tier A keys — must NEVER come from LLM generation (contract 4.7, D3).
TIER_A_KEYS = frozenset({
    "disclosure", "refer_phc", "cannot_advise",
    "readback", "readback_changed", "saved",
})


@lru_cache(maxsize=1)
def _load_yaml() -> dict:
    """Load templates.yaml once and cache.
    WHY: File I/O on every speak() call would slow the voice loop."""
    path = _DATA_DIR / "templates.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_variant(key: str, lang: str, _last_used: dict | None = None) -> str:
    """Return one template string for key+lang.

    For Tier B keys that have multiple variants: pick randomly.
    Never pick the same variant twice in a row (pass _last_used dict to track).

    _last_used: optional dict {key: last_index_used}. Caller owns this dict.
                Pass the session's _last_variant_index dict.

    WHY random variant: Natural-sounding speech avoids robotic repetition.
    """
    data = _load_yaml()

    if key not in data:
        log.warning("Template key '%s' not found in templates.yaml", key)
        return ""

    entry = data[key]
    lang_val = entry.get(lang)

    if lang_val is None:
        log.warning("Template key '%s' has no entry for lang '%s', using en-IN", key, lang)
        lang_val = entry.get("en-IN", "")

    # Tier A: exactly one string per language (never a list)
    if isinstance(lang_val, str):
        return lang_val

    # Tier B: list of 1–3 variants
    if isinstance(lang_val, list):
        if len(lang_val) == 1:
            return lang_val[0]

        # Avoid repeating the same variant twice in a row
        last_idx = (_last_used or {}).get(key, -1)
        candidates = [i for i in range(len(lang_val)) if i != last_idx]
        chosen_idx = random.choice(candidates)

        if _last_used is not None:
            _last_used[key] = chosen_idx

        return lang_val[chosen_idx]

    log.warning("Template key '%s' lang '%s' has unexpected type: %s", key, lang, type(lang_val))
    return ""


def render(key: str, lang: str, vars: dict, _last_used: dict | None = None) -> str:
    """Get a template variant and fill in all {placeholder} values.

    Args:
        key:        Template key e.g. "readback", "ask_id"
        lang:       Session language e.g. "hi-IN"
        vars:       Dict of placeholder values e.g. {"summary": "...", "id": "1042"}
        _last_used: Session dict for anti-repeat tracking (see get_variant)

    Returns:
        Final string ready to send to TTS. Never raises.

    WHY vars must be complete: A missing placeholder would crash .format() —
    we catch that and return a safe fallback rather than crashing the voice session.
    """
    template = get_variant(key, lang, _last_used)

    if not template:
        return ""

    try:
        return template.format(**vars)
    except KeyError as e:
        log.error(
            "Template '%s' missing placeholder %s. vars keys: %s",
            key, e, list(vars.keys())
        )
        # Strip unfilled {} slots so TTS doesn't read them aloud
        return re.sub(r"\{[^}]+\}", "", template).strip()


def get_field_label(field: str, lang: str) -> str:
    """Return spoken display name for a draft field.

    e.g. get_field_label("weight_kg", "hi-IN") → "वज़न"
    Used to build the {fields} placeholder in ask_missing template.
    """
    data = _load_yaml()
    labels = data.get("field_labels", {})
    return labels.get(field, {}).get(lang, field)


def get_visit_type_label(visit_type: str, lang: str) -> str:
    """Return spoken label for a visit type code.

    e.g. get_visit_type_label("NEWBORN", "hi-IN") → "नवजात विज़िट"
    Used to build the {visit_type} placeholder in readback.
    """
    data = _load_yaml()
    labels = data.get("visit_type_labels", {})
    return labels.get(visit_type, {}).get(lang, visit_type)


def get_language_label(target_lang: str, speaker_lang: str) -> str:
    """Return the name of target_lang spoken in speaker_lang.

    e.g. get_language_label("hi-IN", "en-IN") → "Hindi"
    Used for switch_language_ok template.
    """
    data = _load_yaml()
    labels = data.get("language_labels", {})
    return labels.get(target_lang, {}).get(speaker_lang, target_lang)


def get_danger_sign_label(sign_id: str, lang: str) -> str:
    """Return spoken label for a danger sign ID.

    Loads from danger_signs.yaml labels block.
    e.g. get_danger_sign_label("NB_FEVER_OR_COLD", "hi-IN") → "बुखार या ठंडा शरीर"
    """
    path = _DATA_DIR / "danger_signs.yaml"
    with open(path, encoding="utf-8") as f:
        signs = yaml.safe_load(f)

    short = lang.split("-")[0]  # "hi-IN" → "hi"

    for sign in signs:
        if sign["id"] == sign_id:
            labels = sign.get("labels", {})
            return labels.get(short, labels.get("en", sign_id))

    return sign_id


def get_vaccine_spoken_label(vaccine_id: str, lang: str) -> str:
    """Return spoken label for a vaccine ID.

    e.g. get_vaccine_spoken_label("PENTA1", "hi-IN") → "पेंटा एक"
    """
    import json
    path = _DATA_DIR / "vaccine_schedule.json"
    sched = json.loads(path.read_text(encoding="utf-8"))

    short = lang.split("-")[0]  # "hi-IN" → "hi"

    for section in ("child", "mother"):
        for v in sched.get(section, []):
            if v["id"] == vaccine_id:
                spoken = v.get("spoken", {})
                return spoken.get(short, spoken.get("en", vaccine_id))

    return vaccine_id
