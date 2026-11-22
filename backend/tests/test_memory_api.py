from datetime import timedelta
import importlib
import os

from app.config import get_settings
from app.date_utils import today_in_india
from app.repo import memory_repo


def test_memory_followup_route_reads_visits_saved_by_voice_repository(monkeypatch):
    # Import main with the explicit sentinel so this test cannot initialize PostgreSQL.
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "memory"
    get_settings.cache_clear()
    main = importlib.import_module("app.main")
    assert main.repo is memory_repo
    memory_repo.reset_for_testing()
    monkeypatch.setattr(main, "repo", memory_repo)
    today = today_in_india()
    record = {
        "beneficiary_id": "1001",
        "visit_date": today.isoformat(),
        "next_visit_date": (today + timedelta(days=5)).isoformat(),
        "danger_flags": [],
        "flagged": False,
    }

    try:
        memory_repo.save_visit(record, transcript="synthetic test note")
        followups = main.get_followups()
        assert len(followups) == 1
        assert followups[0]["beneficiary_id"] == "1001"
        assert followups[0]["name"]
    finally:
        memory_repo.reset_for_testing()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()
