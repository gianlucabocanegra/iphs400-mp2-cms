"""Time: stored in UTC, shown in America/Lima."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lima(iso: str | None) -> str:
    """A stored UTC timestamp as 'YYYY-MM-DD HH:MM' in Lima time."""
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone(LIMA).strftime("%Y-%m-%d %H:%M")


MONTHS_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def today_lima() -> date:
    return datetime.now(LIMA).date()


def fecha(iso: str | None) -> str:
    """A stored UTC timestamp as a Lima-time Spanish date: '29 de septiembre de 2026'."""
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(LIMA)
    return f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}"
