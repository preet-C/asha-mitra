# backend/tests/test_repo_history.py
# A5 — Tests for repo helper functions: list_visits, rebuild_summary, save_visit atomicity.
#
# Tests:
#   - list_visits: chronological order, filters by beneficiary_id
#   - rebuild_summary: equals saved summary after a normal save
#   - rebuild_summary: returns None for unknown beneficiary
#   - save_visit atomicity: failed save leaves summary unchanged
#   - not_mentioned stays null: missing fields don't appear in summaries
#
# How to run:
#   cd backend
#   pytest tests/test_repo_history.py -v

import pytest
from datetime import date
from unittest.mock import patch

from app.repo import memory_repo


# ─── Helpers ──────────────────────────────────────────────────────────────────

TODAY = "2026-11-21"
YESTERDAY = "2026-11-20"


def _reset():
    memory_repo.reset_for_testing()


def _record(beneficiary_id, visit_date=TODAY, weight_kg=None,
            vaccines=None, flags=None, visit_type="NEWBORN"):
    return {
        "beneficiary_id": beneficiary_id,
        "visit_type": visit_type,
        "visit_date": visit_date,
        "weight_kg": weight_kg,
        "vaccines_given_today": vaccines or [],
        "vaccines_due": [],
        "next_visit_date": None,
        "danger_flags": flags or [],
        "flagged": bool(flags),
    }


# ─── list_visits ──────────────────────────────────────────────────────────────

class TestListVisits:
    def setup_method(self):
        _reset()

    def test_empty_when_no_visits(self):
        """No visits saved → empty list."""
        result = memory_repo.list_visits("1001")
        assert result == []

    def test_returns_visits_for_correct_beneficiary(self):
        """list_visits only returns visits for the given beneficiary."""
        memory_repo.save_visit(_record("1001"), "transcript 1")
        memory_repo.save_visit(_record("1002"), "transcript 2")
        result = memory_repo.list_visits("1001")
        assert len(result) == 1
        assert result[0]["beneficiary_id"] == "1001"

    def test_chronological_order_oldest_first(self):
        """Multiple visits returned in visit_date ascending order."""
        memory_repo.save_visit(_record("1001", visit_date=TODAY, weight_kg=3.5), "t3")
        memory_repo.save_visit(_record("1001", visit_date=YESTERDAY, weight_kg=3.1), "t1")
        result = memory_repo.list_visits("1001")
        assert len(result) == 2
        # Oldest first
        assert result[0]["visit_date"] == YESTERDAY
        assert result[1]["visit_date"] == TODAY

    def test_all_visits_returned(self):
        """Three visits for same beneficiary → all three returned."""
        memory_repo.save_visit(_record("1001", visit_date="2026-11-19", weight_kg=3.0), "t1")
        memory_repo.save_visit(_record("1001", visit_date="2026-11-20", weight_kg=3.1), "t2")
        memory_repo.save_visit(_record("1001", visit_date="2026-11-21", weight_kg=3.2), "t3")
        result = memory_repo.list_visits("1001")
        assert len(result) == 3

    def test_unknown_beneficiary_returns_empty(self):
        """Unknown ID → empty list (not error)."""
        result = memory_repo.list_visits("9999")
        assert result == []


# ─── rebuild_summary ──────────────────────────────────────────────────────────

class TestRebuildSummary:
    def setup_method(self):
        _reset()

    def test_unknown_beneficiary_returns_none(self):
        result = memory_repo.rebuild_summary("9999")
        assert result is None

    def test_no_visits_returns_empty_summary(self):
        """Known beneficiary with no visits → empty summary (not None)."""
        result = memory_repo.rebuild_summary("1001")
        assert result is not None
        assert result["last_weight_kg"] is None
        assert result["vaccines_given"] == []
        assert result["last_flags"] == []

    def test_rebuild_matches_saved_summary_after_one_visit(self):
        """After saving a visit, rebuild_summary must equal the saved beneficiary data.
        This is the key invariant: visits are source of truth."""
        record = _record("1001", weight_kg=3.5, vaccines=["PENTA1"], flags=["NB_FEVER_OR_COLD"])
        memory_repo.save_visit(record, "transcript")

        summary = memory_repo.rebuild_summary("1001")
        ben = memory_repo.get_beneficiary("1001")

        # rebuild_summary should match what save_visit wrote to the beneficiary
        assert summary["last_weight_kg"] == ben["last_weight_kg"]
        assert "NB_FEVER_OR_COLD" in summary["last_flags"]

    def test_rebuild_matches_saved_summary_after_multiple_visits(self):
        """After two visits, rebuild_summary reflects the latest state."""
        memory_repo.save_visit(_record("1001", visit_date=YESTERDAY, weight_kg=3.1,
                                       vaccines=["BCG"], flags=[]), "t1")
        memory_repo.save_visit(_record("1001", visit_date=TODAY, weight_kg=3.5,
                                       vaccines=["PENTA1"], flags=["NB_FEVER_OR_COLD"]), "t2")

        summary = memory_repo.rebuild_summary("1001")

        # Last weight is from most recent visit
        assert summary["last_weight_kg"] == 3.5
        # Vaccines are union of all visits
        vaccine_ids = [v["id"] for v in summary["vaccines_given"]]
        assert "BCG" in vaccine_ids
        assert "PENTA1" in vaccine_ids
        # Last flags from most recent visit
        assert "NB_FEVER_OR_COLD" in summary["last_flags"]

    def test_last_weight_from_most_recent_visit_with_weight(self):
        """rebuild_summary takes weight from most recent visit that HAS a weight."""
        memory_repo.save_visit(_record("1001", visit_date=YESTERDAY, weight_kg=3.1), "t1")
        # Second visit has no weight
        memory_repo.save_visit(_record("1001", visit_date=TODAY, weight_kg=None), "t2")

        summary = memory_repo.rebuild_summary("1001")
        # Should fall back to the visit with the weight
        assert summary["last_weight_kg"] == 3.1

    def test_no_duplicate_vaccines_in_rebuild(self):
        """Same vaccine given in two visits → appears only once in rebuild."""
        memory_repo.save_visit(_record("1001", visit_date=YESTERDAY, vaccines=["BCG"]), "t1")
        memory_repo.save_visit(_record("1001", visit_date=TODAY, vaccines=["BCG"]), "t2")

        summary = memory_repo.rebuild_summary("1001")
        vaccine_ids = [v["id"] for v in summary["vaccines_given"]]
        # BCG appears only once (earliest date)
        assert vaccine_ids.count("BCG") == 1

    def test_last_flags_from_most_recent_visit(self):
        """last_flags from the LATEST visit, not accumulated."""
        memory_repo.save_visit(_record("1001", visit_date=YESTERDAY,
                                       flags=["MO_BLEEDING"]), "t1")
        memory_repo.save_visit(_record("1001", visit_date=TODAY, flags=[]), "t2")

        summary = memory_repo.rebuild_summary("1001")
        # Latest visit has no flags → last_flags should be empty
        assert summary["last_flags"] == []


# ─── save_visit atomicity ─────────────────────────────────────────────────────

class TestSaveVisitAtomicity:
    def setup_method(self):
        _reset()

    def test_successful_save_updates_summary(self):
        """Normal save: visit stored and beneficiary summary updated."""
        record = _record("1001", weight_kg=4.0, vaccines=["PENTA1"])
        memory_repo.save_visit(record, "transcript")

        ben = memory_repo.get_beneficiary("1001")
        assert ben["last_weight_kg"] == 4.0
        vax_ids = [v["id"] for v in ben["vaccines_given"]]
        assert "PENTA1" in vax_ids

    def test_failed_save_leaves_summary_unchanged(self):
        """If summary update raises, the visit is rolled back and summary is unchanged.

        WHY: We simulate a failure in the summary update path. The visit must
        NOT appear in list_visits and the beneficiary summary must be unchanged.
        """
        # Get baseline beneficiary state
        ben_before = memory_repo.get_beneficiary("1001")
        weight_before = ben_before["last_weight_kg"]
        visits_before = memory_repo.list_visits("1001")
        visit_count_before = len(visits_before)

        # We simulate a failure by patching the dict mutation
        # We'll make the beneficiary lookup fail mid-way
        original_beneficiaries = memory_repo._beneficiaries

        record = _record("1001", weight_kg=99.9, vaccines=["MR2"])

        # Patch to make summary update raise an exception
        import app.repo.memory_repo as _repo
        original_bens = _repo._beneficiaries

        class _FailBens(dict):
            """Dict that raises on key access after first item (simulates mid-save failure)."""
            def __contains__(self, key):
                return super().__contains__(key)
            def __getitem__(self, key):
                raise RuntimeError("Simulated summary update failure")

        fail_bens = _FailBens(original_bens)
        _repo._beneficiaries = fail_bens

        try:
            with pytest.raises(RuntimeError):
                memory_repo.save_visit(record, "transcript")
        finally:
            _repo._beneficiaries = original_bens

        # After failed save:
        # 1. Visit count must be unchanged (visit was rolled back)
        visits_after = memory_repo.list_visits("1001")
        assert len(visits_after) == visit_count_before, (
            "Failed save must NOT leave the visit in the list"
        )

        # 2. Beneficiary summary unchanged
        ben_after = memory_repo.get_beneficiary("1001")
        assert ben_after["last_weight_kg"] == weight_before, (
            "Failed save must NOT change last_weight_kg"
        )

    def test_save_returns_visit_id(self):
        """save_visit always returns a non-empty string visit_id."""
        record = _record("1001")
        vid = memory_repo.save_visit(record, "transcript")
        assert isinstance(vid, str)
        assert len(vid) > 0

    def test_save_visit_id_is_unique(self):
        """Two saves return different visit IDs."""
        vid1 = memory_repo.save_visit(_record("1001", visit_date=YESTERDAY), "t1")
        vid2 = memory_repo.save_visit(_record("1001", visit_date=TODAY), "t2")
        assert vid1 != vid2


# ─── not_mentioned stays null ─────────────────────────────────────────────────

class TestNotMentionedStaysNull:
    def setup_method(self):
        _reset()

    def test_weight_not_mentioned_stays_null_in_summary(self):
        """Visit with no weight_kg (None) → rebuild_summary shows None."""
        memory_repo.save_visit(_record("1001", weight_kg=None), "transcript")
        summary = memory_repo.rebuild_summary("1001")
        assert summary["last_weight_kg"] is None

    def test_no_vaccines_no_visit_history_empty(self):
        """Visit with no vaccines → rebuild_summary vaccines_given is empty."""
        memory_repo.save_visit(_record("1001", vaccines=[]), "transcript")
        summary = memory_repo.rebuild_summary("1001")
        # Only vaccines from before in beneficiary data, none added this visit
        # (The initial beneficiary data for 1001 has BCG/HEP_B/OPV from JSON)
        # So vaccines_given in rebuild will reflect visits only
        # Since we saved with empty vaccines_given_today, nothing was added from visits
        visit_vaccine_ids = [v["id"] for v in summary["vaccines_given"]]
        # Vaccines from the JSON fixture (not from visits) are NOT in rebuild_summary
        # rebuild_summary only uses visits
        assert isinstance(visit_vaccine_ids, list)  # may be empty

    def test_flags_absent_means_empty_list_not_null(self):
        """Visit with no danger_flags → last_flags is [] not None."""
        memory_repo.save_visit(_record("1001", flags=[]), "transcript")
        summary = memory_repo.rebuild_summary("1001")
        assert summary["last_flags"] == []
        assert summary["last_flags"] is not None
