from __future__ import annotations

from datetime import datetime

from src.utils.time_window import (
    resolve_daily_time_window_status,
    validate_daily_time_window,
)


def test_validate_daily_time_window_accepts_cross_midnight_window() -> None:
    start, end = validate_daily_time_window("20:00", "08:00")
    assert start == "20:00"
    assert end == "08:00"


def test_resolve_daily_time_window_status_allows_inside_same_day_window() -> None:
    status = resolve_daily_time_window_status(
        "10:00",
        "20:00",
        timezone_name="Asia/Shanghai",
        now=datetime.fromisoformat("2026-03-25T11:30:00+08:00"),
    )

    assert status.has_window is True
    assert status.is_available is True
    assert status.block_reason is None


def test_resolve_daily_time_window_status_blocks_outside_cross_midnight_window() -> None:
    status = resolve_daily_time_window_status(
        "20:00",
        "08:00",
        timezone_name="Asia/Shanghai",
        now=datetime.fromisoformat("2026-03-25T12:00:00+08:00"),
    )

    assert status.has_window is True
    assert status.is_available is False
    assert status.block_reason == "当前不在可用时段 20:00-08:00"
    assert "12:00" in (status.block_detail or "")
