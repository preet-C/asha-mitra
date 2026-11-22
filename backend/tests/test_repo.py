# backend/tests/test_repo.py
# P7 — Tests for pg_repo using in-memory SQLite (no Postgres needed).
#
# WHY SQLite: CI and offline dev work without a database server.
# Same SQLAlchemy models work because we use only dialect-neutral column types.
#
# Run: cd backend && pytest tests/test_repo.py -v

import os
import uuid
from datetime import date, timedelta

import pytest

# ── env setup BEFORE any app import ──────────────────────────────────────────
# WHY before import: config.py and crypto.py read env vars at import time.
# Setting them here ensures the test key / SQLite URL are picked up.

# A valid Fernet key for tests only — never used in production.
_TEST_KEY = "7xDkNn1GWg5V-Mg4at2tf6iMj5WgERPy9ueXRBlGyKQ="
os.environ["TRANSCRIPT_KEY"] = _TEST_KEY
os.environ["DATABASE_URL"] = "sqlite://"  # always override to in-memory SQLite
from app.config import get_settings  # noqa: E402
get_settings.cache_clear()  # prevent cached .env settings from reaching a real database

# ── app imports ───────────────────────────────────────────────────────────────
import app.db as db_module               # noqa: E402
from app.db import create_tables         # noqa: E402
from app.models import Beneficiary       # noqa: E402
import app.repo.pg_repo as repo          # noqa: E402
from app.crypto import encrypt, decrypt  # noqa: E402


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the SQLAlchemy engine and re-create tables before each test.

    WHY autouse: every test starts from a clean slate so they don't
    interfere with each other (no leftover rows, no shared state).
    """
    # Force a brand-new in-memory engine for this test
    db_module._engine = None
    os.environ["DATABASE_URL"] = "sqlite://"
    create_tables()
    yield
    # Teardown: drop engine so the next test gets its own fresh DB
    db_module._engine = None


def _insert_ben(id: str = "1001", kind: str = "child", flags: list | None = None) -> None:
    """Insert a minimal beneficiary row. Used by multiple tests."""
    from app.db import get_session
    with get_session() as session:
        session.add(Beneficiary(
            id=id,
            name=f"Test {id}",
            kind=kind,
            dob="2026-10-01" if kind == "child" else None,
            edd="2027-03-01" if kind == "mother" else None,
            village="Testpur",
            last_weight_kg=3.5,
            vaccines_given=[{"id": "BCG", "date": "2026-10-01"}],
            last_flags=flags or [],
        ))


def _make_record(ben_id: str = "1001", **overrides) -> dict:
    """Build a minimal final visit record (contract 4.2)."""
    r = {
        "beneficiary_id": ben_id,
        "visit_type": "NEWBORN",
        "visit_date": date.today().isoformat(),
        "weight_kg": 3.8,
        "vaccines_given_today": ["PENTA1"],
        "vaccines_due": ["OPV1"],
        "next_visit_date": (date.today() + timedelta(days=5)).isoformat(),
        "danger_flags": [],
        "flagged": False,
    }
    r.update(overrides)
    return r


# ── crypto unit tests ─────────────────────────────────────────────────────────

def test_encrypt_is_not_plaintext():
    """encrypt() must not return the original string."""
    plain = "She said baby has fever."
    token = encrypt(plain)
    assert token != plain
    assert len(token) > 10


def test_decrypt_round_trip():
    """decrypt(encrypt(x)) must equal x."""
    plain = "Nandpur visit notes."
    assert decrypt(encrypt(plain)) == plain


def test_decrypt_bad_token_returns_empty():
    """decrypt() with a garbage token returns "" instead of raising."""
    assert decrypt("not-a-valid-fernet-token") == ""


def test_decrypt_empty_string_returns_empty():
    """decrypt('') returns '' without error."""
    assert decrypt("") == ""


# ── get_beneficiary ───────────────────────────────────────────────────────────

def test_get_beneficiary_found():
    """get_beneficiary returns a dict with the right keys and values."""
    _insert_ben("1001")
    result = repo.get_beneficiary("1001")
    assert result is not None
    assert result["id"] == "1001"
    assert result["name"] == "Test 1001"
    assert result["kind"] == "child"
    assert isinstance(result["vaccines_given"], list)
    assert isinstance(result["last_flags"], list)


def test_get_beneficiary_not_found():
    """get_beneficiary returns None for an unknown ID."""
    result = repo.get_beneficiary("9999")
    assert result is None


def test_get_beneficiary_returns_dict_not_orm():
    """get_beneficiary must return a plain dict, not an ORM object."""
    _insert_ben("1001")
    result = repo.get_beneficiary("1001")
    assert type(result) is dict


# ── save_visit ────────────────────────────────────────────────────────────────

def test_save_visit_returns_valid_uuid():
    """save_visit returns a string that parses as a UUID."""
    _insert_ben("1001")
    visit_id = repo.save_visit(_make_record("1001"), transcript="test notes")
    uuid.UUID(visit_id)   # raises ValueError if not a valid UUID


def test_save_visit_transcript_not_stored_as_plaintext():
    """The transcript column must NOT contain the raw text."""
    _insert_ben("1001")
    plain = "She said baby has fever."
    visit_id = repo.save_visit(_make_record("1001"), transcript=plain)

    from app.db import get_session
    from app.models import Visit
    with get_session() as session:
        visit = session.get(Visit, visit_id)
        enc = visit.transcript_enc   # read INSIDE session to avoid DetachedInstanceError

    assert enc is not None
    assert enc != plain


def test_save_visit_transcript_decrypts_correctly():
    """decrypt(transcript_enc) must equal the original transcript."""
    _insert_ben("1001")
    plain = "Weight three point eight kilo."
    visit_id = repo.save_visit(_make_record("1001"), transcript=plain)

    from app.db import get_session
    from app.models import Visit
    with get_session() as session:
        visit = session.get(Visit, visit_id)
        enc = visit.transcript_enc

    assert decrypt(enc) == plain


def test_save_visit_empty_transcript_stored_as_null():
    """An empty transcript string results in transcript_enc = NULL."""
    _insert_ben("1001")
    visit_id = repo.save_visit(_make_record("1001"), transcript="")

    from app.db import get_session
    from app.models import Visit
    with get_session() as session:
        visit = session.get(Visit, visit_id)
        enc = visit.transcript_enc

    assert enc is None


def test_save_visit_updates_weight():
    """After save_visit, get_beneficiary returns the new weight."""
    _insert_ben("1001")
    repo.save_visit(_make_record("1001", weight_kg=4.5), transcript="weight four five")
    ben = repo.get_beneficiary("1001")
    assert ben["last_weight_kg"] == 4.5


def test_save_visit_appends_new_vaccines():
    """New vaccines from this visit appear in beneficiary.vaccines_given."""
    _insert_ben("1001")
    repo.save_visit(_make_record("1001", vaccines_given_today=["PENTA1", "OPV1"]), transcript="")
    ben = repo.get_beneficiary("1001")
    ids = [v["id"] for v in ben["vaccines_given"]]
    assert "PENTA1" in ids
    assert "OPV1" in ids


def test_save_visit_no_duplicate_vaccines():
    """BCG is already in the fixture — saving BCG again must not duplicate it."""
    _insert_ben("1001")
    repo.save_visit(_make_record("1001", vaccines_given_today=["BCG"]), transcript="")
    ben = repo.get_beneficiary("1001")
    bcg_rows = [v for v in ben["vaccines_given"] if v["id"] == "BCG"]
    assert len(bcg_rows) == 1


def test_save_visit_updates_last_flags():
    """Danger flags from this visit appear in beneficiary.last_flags."""
    _insert_ben("1001")
    repo.save_visit(
        _make_record("1001", danger_flags=["NB_FEVER_OR_COLD"], flagged=True),
        transcript="baby has fever",
    )
    ben = repo.get_beneficiary("1001")
    assert "NB_FEVER_OR_COLD" in ben["last_flags"]


# ── followups / get_followups ─────────────────────────────────────────────────

def test_followups_empty_with_no_visits():
    """followups() returns [] when no visits have been saved."""
    assert repo.followups() == []


def test_followups_shows_upcoming_visit():
    """A visit with next_visit_date within 7 days appears in followups."""
    _insert_ben("1001")
    future = (date.today() + timedelta(days=3)).isoformat()
    repo.save_visit(_make_record("1001", next_visit_date=future), transcript="")
    result = repo.followups()
    assert len(result) == 1
    assert result[0]["next_visit_date"] == future


def test_followups_excludes_far_future_visit():
    """A non-flagged visit beyond 7 days is NOT shown by default."""
    _insert_ben("1001")
    far = (date.today() + timedelta(days=30)).isoformat()
    repo.save_visit(_make_record("1001", next_visit_date=far, flagged=False), transcript="")
    result = repo.followups()
    assert result == []


def test_followups_shows_flagged_past_visit():
    """A flagged visit with a past next_visit_date still appears."""
    _insert_ben("1001")
    past = "2020-01-01"
    repo.save_visit(
        _make_record("1001", next_visit_date=past, flagged=True,
                     danger_flags=["MO_FEVER"]),
        transcript="",
    )
    result = repo.followups()
    assert len(result) == 1
    assert result[0]["flagged"] is True


def test_followups_flagged_before_non_flagged():
    """Flagged visits must come before non-flagged even if date is later."""
    _insert_ben("1001")
    _insert_ben("1002")

    # Non-flagged, earlier date
    repo.save_visit(_make_record("1001", next_visit_date=(date.today() + timedelta(days=1)).isoformat(), flagged=False), transcript="")
    # Flagged, later date
    repo.save_visit(_make_record("1002", next_visit_date=(date.today() + timedelta(days=4)).isoformat(), flagged=True, danger_flags=["NB_CORD_PUS"]), transcript="")

    result = repo.followups()
    assert result[0]["flagged"] is True
    assert result[1]["flagged"] is False


def test_followups_result_shape():
    """Every item in followups() contains the required keys."""
    _insert_ben("1001")
    repo.save_visit(_make_record("1001"), transcript="")
    result = repo.followups()
    assert len(result) == 1
    item = result[0]
    for key in ("visit_id", "beneficiary_id", "name", "village", "kind",
                "next_visit_date", "flagged", "danger_flags"):
        assert key in item, f"Missing key in followup item: {key!r}"


def test_get_followups_days_ahead_param():
    """get_followups(today, days_ahead=14) includes visits beyond 7 days."""
    _insert_ben("1001")
    ten_days = (date.today() + timedelta(days=10)).isoformat()
    repo.save_visit(_make_record("1001", next_visit_date=ten_days, flagged=False), transcript="")

    today_str = date.today().isoformat()
    # days_ahead=7 should NOT include it
    assert repo.get_followups(today_str, days_ahead=7) == []
    # days_ahead=14 SHOULD include it
    assert len(repo.get_followups(today_str, days_ahead=14)) == 1


# ── purge integration ─────────────────────────────────────────────────────────

def test_purge_clears_transcript_enc():
    """After purge (NULL only), transcript_enc is NULL but visit row remains."""
    _insert_ben("1001")
    visit_id = repo.save_visit(_make_record("1001"), transcript="some notes")

    # Run purge logic directly (same SQL as purge.py)
    import sqlalchemy as sa
    from app.db import get_engine
    from app.models import Visit
    with get_engine().begin() as conn:
        conn.execute(sa.update(Visit).values(transcript_enc=None))

    from app.db import get_session
    with get_session() as session:
        visit = session.get(Visit, visit_id)
        enc = visit.transcript_enc

    assert enc is None   # transcript wiped
    # visit row still exists (ID still found)
    with get_session() as s:
        still_there = s.get(Visit, visit_id)
        assert still_there is not None
