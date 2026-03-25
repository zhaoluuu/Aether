"""Helpers for provider-key daily time windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config.settings import config
from src.core.logger import logger


@dataclass(frozen=True, slots=True)
class DailyTimeWindowStatus:
    start: str | None
    end: str | None
    has_window: bool
    is_available: bool
    timezone_name: str
    current_local_time: str | None = None
    invalid_reason: str | None = None

    @property
    def range_text(self) -> str | None:
        if not self.start or not self.end:
            return None
        return f"{self.start}-{self.end}"

    @property
    def block_reason(self) -> str | None:
        if self.is_available:
            return None
        if self.invalid_reason:
            return self.invalid_reason
        if self.range_text:
            return f"当前不在可用时段 {self.range_text}"
        return "当前不在可用时段"

    @property
    def block_detail(self) -> str | None:
        if self.is_available:
            return None
        if self.invalid_reason:
            return self.invalid_reason
        if self.current_local_time and self.range_text:
            return (
                f"当前时间 {self.current_local_time}，可用时段 {self.range_text}"
                f"（{self.timezone_name}）"
            )
        return self.block_reason


def normalize_daily_time_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("时间格式必须为 HH:MM")
    text = value.strip()
    if not text:
        return None

    parts = text.split(":", 1)
    if len(parts) != 2:
        raise ValueError("时间格式必须为 HH:MM")

    hour_text, minute_text = parts
    if not hour_text.isdigit() or not minute_text.isdigit():
        raise ValueError("时间格式必须为 HH:MM")

    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("时间必须在 00:00-23:59 之间")
    return f"{hour:02d}:{minute:02d}"


def validate_daily_time_window(
    start: str | None,
    end: str | None,
) -> tuple[str | None, str | None]:
    normalized_start = normalize_daily_time_text(start)
    normalized_end = normalize_daily_time_text(end)

    if normalized_start is None and normalized_end is None:
        return None, None
    if normalized_start is None or normalized_end is None:
        raise ValueError("启用时间段时必须同时提供开始时间和结束时间")
    if normalized_start == normalized_end:
        raise ValueError("开始时间和结束时间不能相同")
    return normalized_start, normalized_end


def daily_time_to_minutes(value: str) -> int:
    normalized = normalize_daily_time_text(value)
    if normalized is None:
        raise ValueError("时间不能为空")
    hour_text, minute_text = normalized.split(":", 1)
    return int(hour_text) * 60 + int(minute_text)


def _safe_normalize(value: str | None) -> str | None:
    try:
        return normalize_daily_time_text(value)
    except ValueError:
        return str(value).strip() or None


def _resolve_timezone(timezone_name: str | None = None) -> tuple[str, ZoneInfo]:
    tz_name = str(timezone_name or config.app_timezone or "UTC").strip() or "UTC"
    try:
        return tz_name, ZoneInfo(tz_name)
    except Exception:
        logger.warning("Invalid app timezone {}, fallback to UTC for time-window checks", tz_name)
        return "UTC", ZoneInfo("UTC")


def resolve_daily_time_window_status(
    start: str | None,
    end: str | None,
    *,
    timezone_name: str | None = None,
    now: datetime | None = None,
) -> DailyTimeWindowStatus:
    tz_name, tz = _resolve_timezone(timezone_name)

    try:
        normalized_start, normalized_end = validate_daily_time_window(start, end)
    except ValueError as exc:
        return DailyTimeWindowStatus(
            start=_safe_normalize(start),
            end=_safe_normalize(end),
            has_window=bool((start and str(start).strip()) or (end and str(end).strip())),
            is_available=False,
            timezone_name=tz_name,
            invalid_reason=str(exc),
        )

    if normalized_start is None or normalized_end is None:
        return DailyTimeWindowStatus(
            start=None,
            end=None,
            has_window=False,
            is_available=True,
            timezone_name=tz_name,
        )

    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    else:
        current = current.astimezone(tz)

    current_minutes = current.hour * 60 + current.minute
    start_minutes = daily_time_to_minutes(normalized_start)
    end_minutes = daily_time_to_minutes(normalized_end)

    if start_minutes < end_minutes:
        is_available = start_minutes <= current_minutes < end_minutes
    else:
        is_available = current_minutes >= start_minutes or current_minutes < end_minutes

    return DailyTimeWindowStatus(
        start=normalized_start,
        end=normalized_end,
        has_window=True,
        is_available=is_available,
        timezone_name=tz_name,
        current_local_time=f"{current.hour:02d}:{current.minute:02d}",
    )


def resolve_provider_key_time_window_status(
    key: object,
    *,
    timezone_name: str | None = None,
    now: datetime | None = None,
) -> DailyTimeWindowStatus:
    start_value = getattr(key, "time_range_start", None)
    end_value = getattr(key, "time_range_end", None)
    return resolve_daily_time_window_status(
        start_value if isinstance(start_value, str) else None,
        end_value if isinstance(end_value, str) else None,
        timezone_name=timezone_name,
        now=now,
    )
