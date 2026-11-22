"""Calendar dates for ASHA Mitra's India-based visit workflow."""

from datetime import date, datetime, timedelta, timezone


_INDIA = timezone(timedelta(hours=5, minutes=30), name="IST")


def today_in_india(now: datetime | None = None) -> date:
    """Return the current calendar date in India, even when hosted in UTC."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(_INDIA).date()
