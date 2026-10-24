"""Relógio de negócio injetável (avançável pelo simulador) e relógio real separado."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_offset = timedelta(0)


def business_now() -> datetime:
    return datetime.now(timezone.utc) + _offset


def real_now() -> datetime:
    return datetime.now(timezone.utc)


def advance(hours: float) -> datetime:
    global _offset
    _offset += timedelta(hours=hours)
    return business_now()


def set_offset(offset: timedelta) -> None:
    global _offset
    _offset = offset
