# backend/app/repo/pg_repo.py
# P7 — Postgres implementation of the Repo interface (contract 4.4).
#
# WHY this file: dialogue.py calls exactly three functions:
#   get_beneficiary(id)        → dict | None
#   save_visit(record, text)   → str (visit_id)
#   followups()                → list[dict]
#
# This file implements those three AND adds:
#   get_followups(today, days_ahead=7)  — used by /api/followups route directly
#
# Return shapes are IDENTICAL to memory_repo.py so dialogue.py needs zero
# changes when DATABASE_URL is set and main.py swaps the import.
#
# Key behaviour: transcript is ALWAYS encrypted before storage. If crypto
# fails (key missing), save_visit still saves the visit — just without the
# transcript. A missing transcript must not kill a live voice session.

import logging
import uuid
from datetime import date, timedelta

import sqlalchemy as sa

from app.db import get_session
from app.models import Beneficiary, Visit

log = logging.getLogger(__name__)


# ── public interface (contract 4.4) ──────────────────────────────────────────

def get_beneficiary(id: str) -> dict | None:
    """Look up a beneficiary by their 4-digit ID string.

    Returns the beneficiary as a plain dict (same shape as synthetic_beneficiaries.json)
    or None if not found.

    WHY None instead of raise: brain asks worker to re-enter ID (rule: never crash).
    """
    with get_session() as session:
        row = session.get(Beneficiary, str(id))
        if row is None:
            return None
        return _ben_to_dict(row)


def save_visit(record: dict, transcript: str) -> str:
    """Save a completed visit to Postgres and return its visit_id (UUID string).

    Steps:
      1. Encrypt the transcript (uses TRANSCRIPT_KEY from env via crypto.py).
         If encryption fails → save visit without transcript, log warning.
         WHY: a missing TRANSCRIPT_KEY must not crash a live voice session.
      2. Insert a new row into visits.
      3. Update the beneficiary: last_weight_kg, vaccines_given, last_flags.
         WHY update: get_beneficiary() must return fresh data for the next visit
         in the same session. Mirrors memory_repo behaviour exactly.

    Args:
        record:     Final visit dict (contract 4.2). Brain builds this.
        transcript: Raw STT text to encrypt and store.

    Returns:
        visit_id string (UUID).
    """
    visit_id = str(uuid.uuid4())
    today = date.today().isoformat()
    visit_date = record.get("visit_date", today)

    # Encrypt transcript — never store raw speech text (rule 7, D12)
    encrypted: str | None = None
    if transcript:
        try:
            from app.crypto import encrypt
            encrypted = encrypt(transcript)
        except Exception as exc:
            # Log warning but keep going — visit is more important than transcript
            log.warning(
                "Could not encrypt transcript for visit %s: %s. "
                "Saving visit without transcript.",
                visit_id, exc,
            )

    with get_session() as session:
        # 1. Insert visit row
        visit = Visit(
            id=visit_id,
            beneficiary_id=str(record.get("beneficiary_id", "")),
            visit_date=visit_date,
            visit_type=record.get("visit_type"),
            weight_kg=record.get("weight_kg"),
            vaccines_given_today=record.get("vaccines_given_today") or [],
            vaccines_due=record.get("vaccines_due") or [],
            next_visit_date=record.get("next_visit_date"),
            danger_flags=record.get("danger_flags") or [],
            flagged=bool(record.get("flagged", False)),
            transcript_enc=encrypted,
        )
        session.add(visit)

        # 2. Update beneficiary with the latest data from this visit
        ben_id = str(record.get("beneficiary_id", ""))
        ben = session.get(Beneficiary, ben_id)
        if ben:
            # Update weight
            if record.get("weight_kg") is not None:
                ben.last_weight_kg = record["weight_kg"]

            # Append newly given vaccines (avoid duplicates by ID)
            given_today = record.get("vaccines_given_today") or []
            existing = list(ben.vaccines_given or [])  # copy so SA sees the change
            existing_ids = {v["id"] for v in existing}
            for vax_id in given_today:
                if vax_id not in existing_ids:
                    existing.append({"id": vax_id, "date": visit_date})
                    existing_ids.add(vax_id)
            # WHY reassign (not append in-place): SQLAlchemy JSON columns don't
            # track in-place mutations — reassigning marks the column dirty.
            ben.vaccines_given = existing

            # Update last danger flags
            ben.last_flags = record.get("danger_flags") or []

    log.info("Saved visit %s for beneficiary %s", visit_id, record.get("beneficiary_id"))
    return visit_id


def followups() -> list[dict]:
    """Alias for get_followups() with defaults.

    WHY alias: dialogue.py and memory_repo both call followups() with no args.
    Keeping this name means dialogue.py needs zero changes.
    """
    return get_followups(today=date.today().isoformat(), days_ahead=7)


def get_followups(today: str, days_ahead: int = 7) -> list[dict]:
    """Return upcoming visits (within days_ahead days) and all flagged visits.

    Args:
        today:      ISO date string "YYYY-MM-DD" — the reference date.
        days_ahead: Include visits whose next_visit_date is within this many days.
                    Default 7 gives one week ahead — useful for the demo.

    Returns list of dicts with keys:
        visit_id, beneficiary_id, name, village, kind,
        next_visit_date, flagged, danger_flags

    Sorted: flagged first, then by soonest next_visit_date.
    """
    # Compute the cutoff date string — visits due on or before this date are included
    cutoff = (
        date.fromisoformat(today) + timedelta(days=days_ahead)
    ).isoformat()

    with get_session() as session:
        # Include a visit if:
        #   (a) it has a next_visit_date between today and cutoff (upcoming), OR
        #   (b) it is flagged (regardless of date — flagged visits always show)
        rows = session.execute(
            sa.select(Visit, Beneficiary)
            .join(Beneficiary, Visit.beneficiary_id == Beneficiary.id)
            .where(
                sa.or_(
                    # Upcoming: on or after today AND on or before cutoff
                    sa.and_(
                        Visit.next_visit_date >= today,
                        Visit.next_visit_date <= cutoff,
                    ),
                    # Flagged: always show, even if date is in the past
                    Visit.flagged == True,  # noqa: E712 — SQLAlchemy needs == not 'is'
                )
            )
            .order_by(
                # flagged=True (1) sorts before flagged=False (0) with desc
                Visit.flagged.desc(),
                Visit.next_visit_date.asc(),
            )
        ).all()

        # Build result list inside the session so columns are readable
        result = []
        for visit, ben in rows:
            result.append({
                "visit_id": visit.id,
                "beneficiary_id": visit.beneficiary_id,
                "name": ben.name,
                "village": ben.village,
                "kind": ben.kind,
                "next_visit_date": visit.next_visit_date,
                "flagged": visit.flagged,
                "danger_flags": list(visit.danger_flags or []),
            })

    return result


# ── private helper ────────────────────────────────────────────────────────────

def _ben_to_dict(row: Beneficiary) -> dict:
    """Convert a Beneficiary ORM row to a plain dict.

    WHY plain dict: dialogue.py and the brain work with dicts, not ORM objects.
    Shape matches synthetic_beneficiaries.json exactly.
    """
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "dob": row.dob,
        "edd": row.edd,
        "village": row.village,
        "last_weight_kg": row.last_weight_kg,
        "vaccines_given": list(row.vaccines_given or []),
        "last_flags": list(row.last_flags or []),
    }
