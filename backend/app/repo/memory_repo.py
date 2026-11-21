# backend/app/repo/memory_repo.py
# P5 — In-memory repository (Repo interface 4.4)
#
# WHY this file exists: We need a working data layer for P5 that doesn't require
# a database. It loads synthetic_beneficiaries.json into a Python dict at startup.
# P7 replaces this with a Postgres repo (same interface — just swap the import).
#
# Interface (contract 4.4):
#   get_beneficiary(id: str) → dict | None
#   save_visit(record: dict, transcript: str) → str   (returns visit_id)
#   followups() → list[dict]

import json
import pathlib
import uuid
import logging
from datetime import date, datetime

log = logging.getLogger(__name__)

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


def _load_beneficiaries() -> dict:
    """Load synthetic beneficiaries from JSON into a dict keyed by ID.
    WHY dict: O(1) lookup by ID during voice session."""
    path = _DATA_DIR / "synthetic_beneficiaries.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {b["id"]: b for b in raw}


# In-memory stores. Module-level so they persist across calls within one server run.
_beneficiaries: dict = _load_beneficiaries()
_visits: list[dict] = []  # saved visit records (grows over session)


def get_beneficiary(id: str) -> dict | None:
    """Look up a beneficiary by their 4-digit ID string.

    Returns the beneficiary dict or None if not found.
    WHY None instead of raise: brain asks worker to re-enter ID (rule: never crash).
    """
    return _beneficiaries.get(str(id))


def save_visit(record: dict, transcript: str) -> str:
    """Save a completed visit record and return its unique visit_id.

    Args:
        record:     Final visit dict (contract 4.2). Brain builds this.
        transcript: Raw STT text. In memory we store it as-is (synthetic only).
                    WHY note: P7 (Postgres repo) will encrypt this with Fernet.
                    In memory we keep it because we never store audio and synthetic
                    data has no privacy concern.

    Returns:
        visit_id string (UUID).

    Also updates the in-memory beneficiary record (last_weight_kg, vaccines_given,
    last_flags) so followups() and future visits see the latest data.
    WHY update: P7 does this in Postgres; we mirror that behaviour here so the
    interface contract is identical.
    """
    visit_id = str(uuid.uuid4())

    # Store visit
    full = {**record, "id": visit_id, "transcript": transcript}
    _visits.append(full)
    log.info("Saved visit %s for beneficiary %s", visit_id, record.get("beneficiary_id"))

    # Update beneficiary record so future visits see current state
    ben_id = record.get("beneficiary_id")
    if ben_id and ben_id in _beneficiaries:
        ben = _beneficiaries[ben_id]

        # Update last weight
        if record.get("weight_kg") is not None:
            ben["last_weight_kg"] = record["weight_kg"]

        # Append newly given vaccines (avoid duplicates)
        given_today = record.get("vaccines_given_today") or []
        visit_date_str = record.get("visit_date", date.today().isoformat())
        existing_ids = {v["id"] for v in ben.get("vaccines_given", [])}
        for vax_id in given_today:
            if vax_id not in existing_ids:
                ben.setdefault("vaccines_given", []).append({
                    "id": vax_id,
                    "date": visit_date_str,
                })

        # Update last danger flags
        ben["last_flags"] = record.get("danger_flags", [])

    return visit_id


def followups() -> list[dict]:
    """Return upcoming visits and flagged records for the follow-up list.

    Returns list of dicts with keys: id, name, village, next_visit_date, flagged.
    Sorted: flagged visits first, then by soonest next_visit_date.

    WHY this shape: matches the UI contract (P8) and P7 Postgres repo.
    """
    today_str = date.today().isoformat()
    result = []

    # Collect all visits that have a next_visit_date in the future
    for visit in _visits:
        ben_id = visit.get("beneficiary_id")
        ben = _beneficiaries.get(ben_id, {})
        next_date = visit.get("next_visit_date")
        flagged = visit.get("flagged", False)

        # Include if upcoming or flagged
        if (next_date and next_date >= today_str) or flagged:
            result.append({
                "visit_id": visit.get("id"),
                "beneficiary_id": ben_id,
                "name": ben.get("name", ""),
                "village": ben.get("village", ""),
                "next_visit_date": next_date,
                "flagged": flagged,
                "danger_flags": visit.get("danger_flags", []),
            })

    # Sort: flagged first, then by next_visit_date ascending
    result.sort(key=lambda r: (
        0 if r["flagged"] else 1,
        r["next_visit_date"] or "9999-12-31",
    ))

    return result


def reset_for_testing() -> None:
    """Clear visits and reload beneficiaries from file. Used in tests only.
    WHY: Tests must start from a clean state so they don't interfere with each other."""
    global _beneficiaries, _visits
    _beneficiaries = _load_beneficiaries()
    _visits = []
