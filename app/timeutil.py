"""Time: stored in UTC, shown in America/Lima."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lima(iso: str | None) -> str:
    """A stored UTC timestamp as 'YYYY-MM-DD HH:MM' in Lima time."""
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone(LIMA).strftime("%Y-%m-%d %H:%M")
