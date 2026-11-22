from datetime import date, datetime, timezone

from app.date_utils import today_in_india


def test_date_uses_india_calendar_after_utc_midnight_boundary():
    before_india_midnight = datetime(2026, 11, 21, 17, 0, tzinfo=timezone.utc)
    after_india_midnight = datetime(2026, 11, 21, 19, 0, tzinfo=timezone.utc)

    assert today_in_india(before_india_midnight) == date(2026, 11, 21)
    assert today_in_india(after_india_midnight) == date(2026, 11, 22)
