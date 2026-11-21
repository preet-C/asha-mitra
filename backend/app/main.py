# backend/app/main.py
# FastAPI application — routes and startup.
#
# P7 adds:
#   - lifespan: creates DB tables at startup
#   - GET /api/beneficiaries/{id}  → pg_repo.get_beneficiary
#   - GET /api/followups           → pg_repo.get_followups(today, days_ahead=7)
#
# Repo switcher: DATABASE_URL set → pg_repo. Empty → memory_repo (P5a fallback).
# dialogue.py uses session["repo"] injected by the WebSocket gateway (P10).
# These two REST routes use pg_repo directly because they are always DB-backed.
#
# RULE: WebSocket routes go ABOVE the marked comment line (P9, P10).
# RULE: Static frontend mount goes at the very END (P11).

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException

from app.config import get_settings


# ── repo switcher ─────────────────────────────────────────────────────────────
# dialogue.py and brain code use this via the session object (injected in P10).
# Simple rule: DATABASE_URL set → Postgres repo; empty → in-memory repo.

def _get_repo():
    """Return the correct repo module based on DATABASE_URL env var."""
    if get_settings().DATABASE_URL:
        import app.repo.pg_repo as _repo
    else:
        import app.repo.memory_repo as _repo  # type: ignore[no-redef]
    return _repo


repo = _get_repo()


# ── lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run once at startup, before the app accepts requests.

    WHY lifespan: FastAPI recommends this over @app.on_event (deprecated v0.93+).
    """
    if get_settings().DATABASE_URL:
        from app.db import create_tables
        create_tables()
        print("DB tables ready.")
    yield
    # Nothing to clean up on shutdown for now


app = FastAPI(title="ASHA Mitra", lifespan=lifespan)


# ── health check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True}


# ── P7 routes — add new routes ABOVE the WebSocket comment line ───────────────

@app.get("/api/beneficiaries/{id}")
def get_beneficiary(id: str):
    """Return one beneficiary's current data by their 4-digit ID.

    Used by the UI handshake (session start) to pre-fill the card header
    with name, village, kind before the worker speaks their first note.

    Returns 404 if the ID is not in the database — brain asks worker to retry.
    Uses pg_repo directly (not memory_repo) — always needs a live DB.
    """
    import app.repo.pg_repo as pg_repo
    ben = pg_repo.get_beneficiary(id)
    if ben is None:
        raise HTTPException(status_code=404, detail=f"Beneficiary {id!r} not found.")
    return ben


@app.get("/api/followups")
def get_followups(days_ahead: int = 7):
    """Return upcoming visits (within days_ahead days) + all flagged visits.

    Used by the Follow-ups tab (P8). Sorted: flagged first, then by date.
    Default days_ahead=7 gives one week ahead — covers a typical demo window.
    Pass ?days_ahead=30 to show a wider range.

    Uses pg_repo directly (not memory_repo) — always needs a live DB.
    """
    import app.repo.pg_repo as pg_repo
    today = date.today().isoformat()
    return pg_repo.get_followups(today=today, days_ahead=days_ahead)


# WebSocket routes go ABOVE this line (P9, P10).
# Static frontend mount goes at the very END (P11).
