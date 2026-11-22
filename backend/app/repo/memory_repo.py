"""Synthetic in-memory storage used when DATABASE_URL is empty."""

import json
import logging
import pathlib
import uuid
from copy import deepcopy
from datetime import date, timedelta

from app.date_utils import today_in_india

log = logging.getLogger(__name__)
_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


def _load_beneficiaries() -> dict:
    path = _DATA_DIR / "synthetic_beneficiaries.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(person["id"]): person for person in raw}


_beneficiaries: dict = _load_beneficiaries()
_visits: list[dict] = []


def get_beneficiary(id: str) -> dict | None:
    """Return a copy so a visit session cannot mutate the shared store."""
    beneficiary = _beneficiaries.get(str(id))
    return deepcopy(beneficiary) if beneficiary is not None else None


def save_visit(record: dict, transcript: str) -> str:
    """Save one synthetic visit and update that beneficiary atomically."""
    visit_id = str(uuid.uuid4())
    visit_date = record.get("visit_date", today_in_india().isoformat())
    full_visit = deepcopy({**record, "id": visit_id, "transcript": transcript})

    # Build the new summary before changing either in-memory collection.
    beneficiary_id = str(record.get("beneficiary_id", ""))
    updated_beneficiary = None
    if beneficiary_id in _beneficiaries:
        updated_beneficiary = deepcopy(_beneficiaries[beneficiary_id])
        if record.get("weight_kg") is not None:
            updated_beneficiary["last_weight_kg"] = record["weight_kg"]

        vaccines = list(updated_beneficiary.get("vaccines_given", []))
        known_ids = {item.get("id") for item in vaccines}
        for vaccine_id in record.get("vaccines_given_today") or []:
            if vaccine_id not in known_ids:
                vaccines.append({"id": vaccine_id, "date": visit_date})
                known_ids.add(vaccine_id)
        updated_beneficiary["vaccines_given"] = vaccines
        updated_beneficiary["last_flags"] = list(record.get("danger_flags") or [])

    _visits.append(full_visit)
    try:
        if updated_beneficiary is not None:
            _beneficiaries[beneficiary_id] = updated_beneficiary
    except Exception:
        # Keep the visit list and beneficiary summary in sync if the update fails.
        _visits.pop()
        raise

    log.info("Saved visit %s for beneficiary %s", visit_id, beneficiary_id)
    return visit_id


def list_visits(beneficiary_id: str) -> list[dict]:
    """Return one beneficiary's visits in chronological order."""
    visits = [
        visit for visit in _visits
        if str(visit.get("beneficiary_id", "")) == str(beneficiary_id)
    ]
    visits.sort(key=lambda visit: (visit.get("visit_date") or "", visit.get("id") or ""))
    return deepcopy(visits)


def rebuild_summary(beneficiary_id: str) -> dict | None:
    """Rebuild the current weight, vaccine and danger summary from visits."""
    beneficiary = _beneficiaries.get(str(beneficiary_id))
    if beneficiary is None:
        return None

    visits = list_visits(beneficiary_id)
    summary = deepcopy(beneficiary)
    summary["last_weight_kg"] = next(
        (visit.get("weight_kg") for visit in reversed(visits)
         if visit.get("weight_kg") is not None),
        None,
    )

    vaccines_by_id = {}
    for visit in visits:
        for vaccine_id in visit.get("vaccines_given_today") or []:
            vaccines_by_id.setdefault(vaccine_id, {
                "id": vaccine_id,
                "date": visit.get("visit_date"),
            })
    summary["vaccines_given"] = list(vaccines_by_id.values())
    summary["last_flags"] = list(visits[-1].get("danger_flags") or []) if visits else []
    return summary


def followups() -> list[dict]:
    """Return upcoming visits in the default seven-day window."""
    return get_followups(today=today_in_india().isoformat(), days_ahead=7)


def get_followups(today: str, days_ahead: int = 7) -> list[dict]:
    """Return upcoming or flagged visits with the same shape as PostgreSQL."""
    start = date.fromisoformat(today)
    cutoff = (start + timedelta(days=max(0, days_ahead))).isoformat()
    result = []

    for visit in _visits:
        beneficiary_id = str(visit.get("beneficiary_id", ""))
        beneficiary = _beneficiaries.get(beneficiary_id, {})
        next_date = visit.get("next_visit_date")
        danger_flags = list(visit.get("danger_flags") or [])
        flagged = bool(visit.get("flagged") or danger_flags)
        upcoming = next_date is not None and today <= next_date <= cutoff
        if not upcoming and not flagged:
            continue

        result.append({
            "visit_id": visit.get("id"),
            "beneficiary_id": beneficiary_id,
            "name": beneficiary.get("name", ""),
            "village": beneficiary.get("village", ""),
            "kind": beneficiary.get("kind", ""),
            "next_visit_date": next_date,
            "flagged": flagged,
            "danger_flags": danger_flags,
        })

    result.sort(key=lambda item: (
        0 if item["flagged"] else 1,
        item["next_visit_date"] or "9999-12-31",
    ))
    return result


def reset_for_testing() -> None:
    """Reset the synthetic store so tests cannot affect each other."""
    global _beneficiaries, _visits
    _beneficiaries = _load_beneficiaries()
    _visits = []
