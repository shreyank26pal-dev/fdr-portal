"""Single source of 'now' for the whole backend.

In DEMO_MODE an admin can shift the clock forward ("simulate +85 days") so that
reminders, escalations and maturity transitions can be shown live on stage.
The offset is persisted in system_config and cached here.
"""
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

_offset_days: int = 0


def set_offset_days(days: int) -> None:
    global _offset_days
    _offset_days = int(days)


def offset_days() -> int:
    return _offset_days


def now() -> datetime:
    """Timezone-aware UTC now, shifted by the simulated offset."""
    return datetime.now(timezone.utc) + timedelta(days=_offset_days)


def today() -> date:
    """Today's date in India (IST), shifted by the simulated offset."""
    return now().astimezone(IST).date()
