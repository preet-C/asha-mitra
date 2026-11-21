# backend/app/brain/vaccines.py
# P3 — Vaccine due calculator
# WHY: Determines which vaccines are due for a beneficiary today.
#      Uses the government schedule (vaccine_schedule.json). Pure Python, no LLM.
#      Returns IDs in schedule order so the agent reads them in the right sequence.

import json
import pathlib
from datetime import date
from functools import lru_cache

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def _load_schedule() -> dict:
    """Load vaccine_schedule.json once and cache it."""
    path = _DATA_DIR / "vaccine_schedule.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def vaccines_due(
    kind: str,
    dob_or_none: date | None,
    given_ids: list[str],
    today: date,
) -> list[str]:
    """Return vaccine IDs that are due today but not yet given.

    Args:
        kind:        "child" | "mother"
        dob_or_none: Date of birth (child) or None if unknown.
                     WHY: If DOB unknown we return [] and let dialogue.py ask for it.
                     Not_mentioned ≠ absent (AGENTS rule 4). Never assume no vaccines due.
        given_ids:   List of vaccine IDs already given (from beneficiary record).
        today:       Date of the visit (usually date.today()).

    Returns:
        List of vaccine IDs due (not yet given), in schedule order.
        Empty list means either none are due OR DOB is unknown (caller must distinguish).

    Mother logic (Td1/Td2):
        - Td1 is always due if not given.
        - Td2 is due if Td1 is given AND at least 4 weeks have passed since Td1.
          If Td1 given date is not available, Td2 is listed as due (safe side).
    """
    schedule = _load_schedule()
    given_set = set(given_ids or [])
    due: list[str] = []

    if kind == "child":
        if dob_or_none is None:
            # Cannot compute — return empty. Caller (dialogue.py) should ask for DOB.
            # WHY: Returning [] with unknown DOB is documented here so the caller
            #      doesn't misinterpret it as "no vaccines due".
            return []

        age_days = (today - dob_or_none).days
        age_weeks = age_days / 7  # fractional weeks

        for entry in schedule.get("child", []):
            vax_id = entry["id"]
            due_weeks = entry.get("due_weeks", 0)
            if age_weeks >= due_weeks and vax_id not in given_set:
                due.append(vax_id)

    elif kind == "mother":
        # Td1: due if not given
        if "TD1" not in given_set:
            due.append("TD1")
        else:
            # Td2: due if Td1 given and TD2 not given.
            # We do not have Td1 given-date available here (only given_ids list).
            # Safe-side: if Td1 is given and Td2 is not, list Td2 as due.
            # Dialogue (P5) will show it and worker can confirm or skip.
            if "TD2" not in given_set:
                due.append("TD2")

    return due
