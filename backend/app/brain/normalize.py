# backend/app/brain/normalize.py
# P2 — Normalisers
# WHY: STT gives messy spoken text. We need clean Python values (numbers, dates, IDs)
#      for the brain to work with, and spoken words back for TTS read-back.
#      These are pure Python helpers — no network, no LLM, fully testable offline.

import re
import pathlib
from datetime import date, timedelta
from functools import lru_cache

import yaml
from num2words import num2words  # English only. Do NOT use for hi or kn.

# ─── Load number tables from P1 data file ─────────────────────────────────────

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def _load_tables() -> dict:
    """Load number_words.yaml once and cache it.
    WHY: File I/O on every call would slow down read-back inside a voice loop."""
    path = _DATA_DIR / "number_words.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── ID parsing ───────────────────────────────────────────────────────────────

# Mapping of spoken digit words to their digit character.
# Covers Hindi (Devanagari + romanised), Kannada (Kannada script + romanised), English.
_WORD_TO_DIGIT = {
    # English
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi romanised
    "shunya": "0", "ek": "1", "do": "2", "teen": "3", "chaar": "4", "char": "4",
    "paanch": "5", "panch": "5", "chhah": "6", "chhe": "6", "saat": "7",
    "aath": "8", "nau": "9", "nav": "9",
    # Hindi Devanagari script
    "शून्य": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
    "पाँच": "5", "छह": "6", "सात": "7", "आठ": "8", "नौ": "9",
    # Kannada romanised
    "shunya": "0", "ondu": "1", "eradu": "2", "muru": "3", "mooru": "3",
    "nalku": "4", "naaku": "4", "aidu": "5", "aaru": "6", "elu": "7",
    "entu": "8", "ombattu": "9",
    # Kannada script
    "ಶೂನ್ಯ": "0", "ಒಂದು": "1", "ಎರಡು": "2", "ಮೂರು": "3", "ನಾಲ್ಕು": "4",
    "ಐದು": "5", "ಆರು": "6", "ಏಳು": "7", "ಎಂಟು": "8", "ಒಂಬತ್ತು": "9",
}


def parse_beneficiary_id(text: str) -> str | None:
    """Convert spoken/typed beneficiary ID text to a 4-digit string.

    Accepts: "1042", "1 0 4 2", "one zero four two", "ek zero chaar do",
             "ek shunya chaar do", etc.
    Returns: "1042" (exactly 4 digits), or None if conversion fails.

    WHY: ID must be exact. We do not guess or truncate. 4 digits = contract.
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()

    # Case 1: already a plain 4-digit number
    if re.fullmatch(r"\d{4}", text):
        return text

    # Case 2: digits with spaces e.g. "1 0 4 2"
    no_spaces = text.replace(" ", "")
    if re.fullmatch(r"\d{4}", no_spaces):
        return no_spaces

    # Case 3: spoken words — split and map each token to a digit
    tokens = text.lower().split()
    digits = []
    for token in tokens:
        # Strip punctuation from token
        token_clean = re.sub(r"[^\w\u0900-\u097F\u0C80-\u0CFF]", "", token)
        if token_clean in _WORD_TO_DIGIT:
            digits.append(_WORD_TO_DIGIT[token_clean])
        elif re.fullmatch(r"\d", token_clean):
            digits.append(token_clean)
        else:
            # Unrecognised token — cannot safely continue
            return None

    if len(digits) == 4:
        return "".join(digits)

    return None


# ─── Weight validation ────────────────────────────────────────────────────────

# Biologically plausible ranges per beneficiary kind.
# WHY: These are hard limits — a child at 30 kg or a mother at 10 kg is a data error.
_WEIGHT_RANGES = {
    "child":  (1.0,  25.0),
    "mother": (30.0, 120.0),
}


def validate_weight_kg(value: float, kind: str) -> float | None:
    """Return weight rounded to 1 decimal if in plausible range, else None.

    Args:
        value: weight in kg (float)
        kind:  "child" or "mother"

    WHY: Never silently save an impossible weight. Caller must ask worker to repeat.
    """
    if value is None or not isinstance(value, (int, float)):
        return None
    if kind not in _WEIGHT_RANGES:
        return None
    lo, hi = _WEIGHT_RANGES[kind]
    rounded = round(float(value), 1)
    if lo <= rounded <= hi:
        return rounded
    return None


def parse_weight_fallback(text: str) -> float | None:
    """Parse weight from raw text when LLM extraction fails.

    Understands: "2.8", "2.8 kg", "2800 gram", "2 kilo 800 gram",
                 "do kilo aath sau gram", "800 gram", "aath sau gram".

    WHY: LLM can crash or return broken JSON. Demo must never stop.
    Returns: weight in kg as float, or None.

    NOTE: Does NOT validate range — call validate_weight_kg() after this.
    """
    if not text or not isinstance(text, str):
        return None

    t = text.lower().strip()

    # Pattern: "X kilo Y gram" or "X kilo Y hundred gram" with digit or word parts
    # First normalise spoken numbers that are common in fallback context
    _spoken_to_num = {
        "aath": 8, "ath": 8, "do": 2, "teen": 3, "chaar": 4, "char": 4,
        "paanch": 5, "chhah": 6, "saat": 7, "nau": 9, "ek": 1,
        "sau": 100,  # Hindi "hundred"
        "eradu": 2, "mooru": 3, "naaku": 4, "aidu": 5, "aaru": 6,
        "elu": 7, "entu": 8, "ombattu": 9, "nooru": 100,  # Kannada "hundred"
    }

    # Case 1: "X kilo Y gram" with numeric digits — MUST come before gram-only check
    # e.g. "2 kilo 800 gram" → 2.8 kg
    m = re.search(r"(\d+)\s*kilo(?:gram)?s?\s+(\d+)\s*g(?:ram)?s?", t)
    if m:
        kg = int(m.group(1))
        g = int(m.group(2))
        return round(kg + g / 1000, 1)

    # Case 2: "X kilo" only (no gram part)
    m = re.search(r"(\d+)\s*kilo(?:gram)?s?", t)
    if m:
        return float(m.group(1))

    # Case 3: "X gram" only  e.g. "2800 gram" or "800 gram"
    m = re.search(r"(\d+)\s*g(?:ram)?s?", t)
    if m:
        return round(int(m.group(1)) / 1000, 1)

    # Case 4: plain decimal "2.8" or "2.8 kg" (fallback)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg)?$", t)
    if m:
        val = float(m.group(1))
        # Distinguish grams-only: if no decimal and value >= 500, treat as grams
        if val >= 500 and "." not in m.group(1):
            return round(val / 1000, 1)
        return round(val, 1)

    return None


# ─── Date resolver ─────────────────────────────────────────────────────────────

def resolve_next_visit(spec: dict, today: date) -> date | None:
    """Convert LLM next_visit spec to a concrete date.

    spec shapes (from contract 4.1):
        {"kind": "relative_days", "n": 15}
        {"kind": "weekday", "weekday": 1, "which": "this|next"}
            weekday: 0=Monday … 6=Sunday  (ISO, matches Python date.weekday())
        {"kind": "absolute", "day": 15, "month": 12, "year": null}

    Returns: date object, or None if spec is invalid or resolves to past date.
    WHY: LLM gives structured spec; Python computes final date (contract 4.1 rule).
    """
    if not spec or not isinstance(spec, dict):
        return None

    kind = spec.get("kind")

    if kind == "relative_days":
        n = spec.get("n")
        if not isinstance(n, int) or n <= 0:
            return None
        result = today + timedelta(days=n)
        return result  # relative is always in future

    if kind == "weekday":
        target_wd = spec.get("weekday")
        which = spec.get("which", "next")
        if not isinstance(target_wd, int) or target_wd not in range(7):
            return None
        today_wd = today.weekday()
        days_ahead = (target_wd - today_wd) % 7
        if days_ahead == 0:
            # Today is that weekday
            if which == "next":
                days_ahead = 7  # explicitly "next" means the FOLLOWING week
            else:
                days_ahead = 7  # "this" on the same day also means next occurrence
        result = today + timedelta(days=days_ahead)
        return result  # always future

    if kind == "absolute":
        day = spec.get("day")
        month = spec.get("month")
        year = spec.get("year")
        if not isinstance(day, int) or not isinstance(month, int):
            return None
        if year is None:
            # Pick next upcoming occurrence of this day+month
            year = today.year
            try:
                candidate = date(year, month, day)
            except ValueError:
                return None  # invalid day/month combo
            if candidate <= today:
                candidate = date(year + 1, month, day)
        else:
            try:
                candidate = date(year, month, day)
            except ValueError:
                return None
        if candidate <= today:
            # Date is in the past — data error, do not silently accept
            return None
        return candidate

    return None


# ─── Number → words (for TTS read-back) ───────────────────────────────────────

def number_to_words_en(x: float) -> str:
    """Convert a float to English words. 2.8 → "two point eight".

    WHY: Gnani TTS reads natural words better than digits as strings.
    Uses num2words (English only — do NOT use for hi/kn).
    """
    # num2words handles floats correctly for English
    return num2words(x, lang="en")


def digits_to_words(s: str, lang: str) -> str:
    """Convert a digit string to spoken words, digit by digit.

    "1042" → "ek shunya chaar do" (hi) / "ondu shunya naaku eradu" (kn)
    WHY: IDs are always read digit-by-digit (D6). Never as a combined number.

    lang: "hi-IN" | "kn-IN" | "en-IN"
    """
    if not s or not re.fullmatch(r"\d+", s):
        return s  # return as-is if not pure digits

    tables = _load_tables()
    base_lang = lang.split("-")[0]  # "hi-IN" → "hi"

    if base_lang in ("hi", "kn"):
        digit_map = tables[base_lang]["digits"]
        return " ".join(str(digit_map[int(ch)]) for ch in s)
    else:
        # English: use num2words word for each digit
        _en_digit_words = {
            "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
            "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        }
        return " ".join(_en_digit_words[ch] for ch in s)


def date_to_words(d: date, lang: str) -> str:
    """Convert a date to spoken words: "fifteen December" / "pandrah December".

    Format: DAY MONTH (no year — matches how ASHA workers speak dates).
    WHY: Month names are language-specific; day uses number tables.

    lang: "hi-IN" | "kn-IN" | "en-IN"
    """
    tables = _load_tables()
    base_lang = lang.split("-")[0]

    month_name = tables[base_lang]["months"][d.month]

    if base_lang in ("hi", "kn"):
        # Day as a number word from the numbers map (1–31)
        day_word = str(tables[base_lang]["numbers"][d.day])
    else:
        # English: use num2words ordinal-style but plan says "fifteen December" not "15th"
        day_word = num2words(d.day, lang="en")

    return f"{day_word} {month_name}"


def weight_to_words(kg: float, lang: str) -> str:
    """Convert kg weight to spoken words: 2.8 → "two kilo eight hundred gram".

    WHY (D6): TTS reads "2.8" poorly. ASHA workers understand kilo+gram phrasing.
    Never uses "point". Splits into whole kg + gram remainder.

    lang: "hi-IN" | "kn-IN" | "en-IN"
    """
    tables = _load_tables()
    base_lang = lang.split("-")[0]

    whole_kg = int(kg)
    gram_remainder = round((kg - whole_kg) * 1000)
    # Round gram to nearest 100 for natural speech (2.85 → 900 g, 2.80 → 800 g)
    gram_hundred = round(gram_remainder / 100) * 100

    units = tables[base_lang].get("weight_units", {"kilo": "kilo", "gram": "gram"})
    kilo_word = units["kilo"]
    gram_word = units["gram"]

    if base_lang in ("hi", "kn"):
        num_map = tables[base_lang]["numbers"]
        hundred_map = tables[base_lang]["hundreds"]

        kg_spoken = str(num_map[whole_kg]) if whole_kg <= 99 else str(whole_kg)

        if gram_hundred == 0:
            return f"{kg_spoken} {kilo_word}"
        gram_spoken = str(hundred_map[gram_hundred])
        return f"{kg_spoken} {kilo_word} {gram_spoken} {gram_word}"
    else:
        # English
        kg_spoken = num2words(whole_kg, lang="en")
        if gram_hundred == 0:
            return f"{kg_spoken} kilo"
        gram_spoken = num2words(gram_hundred, lang="en")
        return f"{kg_spoken} kilo {gram_spoken} gram"


def render_number(lang: str, kind: str, value) -> str:
    """Single entry point for all number rendering. Called by speak().

    Args:
        lang:  "hi-IN" | "kn-IN" | "en-IN"
        kind:  "weight" | "id" | "date" | "count"
        value: float for weight/count, str for id, date for date

    WHY: speak() must never call number helpers directly — this one function
         reads the style setting from number_words.yaml and routes accordingly.
         Changing style in the YAML is enough to change all read-back behaviour.
    """
    tables = _load_tables()
    base_lang = lang.split("-")[0]
    style = tables.get(base_lang, {}).get("style", "english")

    if kind == "weight":
        kg = float(value)
        if style == "digits":
            # e.g. "2 point 8" digit style — still no raw "2.8", speak digit by digit
            return digits_to_words(str(int(kg)), lang) + " point " + digits_to_words(
                str(round((kg - int(kg)) * 10)), lang
            )
        return weight_to_words(kg, lang)

    if kind == "id":
        # Always digit-by-digit regardless of style (D6)
        return digits_to_words(str(value), lang)

    if kind == "date":
        return date_to_words(value, lang)

    if kind == "count":
        n = int(value)
        if style == "digits":
            return digits_to_words(str(n), lang)
        if base_lang in ("hi", "kn"):
            num_map = tables[base_lang]["numbers"]
            if n in num_map:
                return str(num_map[n])
            return str(n)
        return num2words(n, lang="en")

    # Unknown kind — return string representation as fallback
    return str(value)


# ─── Spoken number → int (reverse lookup, for ID/weight parsing from STT) ─────

def parse_spoken_number(text: str, lang: str) -> int | None:
    """Parse a spoken number from STT output back to an integer.

    Scope: single numbers 0–99 (sufficient for ID digits, weight whole part,
           and day numbers). Compound numbers e.g. "barah sau" are out of scope
           — LLM handles those; this is a fallback for simple cases.

    Returns: int or None if not recognised.
    WHY: STT sometimes returns native script or romanised words instead of digits.
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip().lower()

    # Try direct digit parse first
    if re.fullmatch(r"\d+", text):
        return int(text)

    tables = _load_tables()
    base_lang = lang.split("-")[0]

    if base_lang not in ("hi", "kn"):
        # English — use _WORD_TO_DIGIT for single words
        result = _WORD_TO_DIGIT.get(text)
        return int(result) if result is not None else None

    # Build reverse lookup: word → number, from both numbers and digits maps
    rev = {}
    lang_data = tables.get(base_lang, {})
    for section in ("digits", "numbers"):
        for num, word in lang_data.get(section, {}).items():
            rev[str(word).lower()] = int(num)

    return rev.get(text)
