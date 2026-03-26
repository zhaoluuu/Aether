"""CC Switch 等客户端使用的 API Key 用量状态查询端点。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session, joinedload

from src.database import get_db
from src.models.database import ApiKey
from src.services.usage.query import UsageQueryMixin

router = APIRouter(tags=["System Catalog"])


def _build_usage_payload(
    *,
    is_active: bool,
    is_valid: bool,
    quota_exhausted: bool,
    remaining: float | None,
    message: str,
    reason: str,
) -> dict[str, Any]:
    """构造统一的用量状态响应，方便客户端稳定解析。"""
    return {
        "status": reason,
        "reason": reason,
        "is_active": is_active,
        "is_valid": is_valid,
        "quota_exhausted": quota_exhausted,
        "remaining": remaining,
        "balance": remaining,
        "unit": "USD",
        "message": message,
    }


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


def _load_api_key_record_for_usage(db: Session, raw_api_key: str) -> ApiKey | None:
    key_hash = ApiKey.hash_key(raw_api_key)
    return (
        db.query(ApiKey)
        .options(joinedload(ApiKey.user))
        .filter(ApiKey.key_hash == key_hash)
        .first()
    )


def _normalize_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_usage_status(db: Session, raw_api_key: str | None) -> dict[str, Any]:
    if not raw_api_key:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="未提供有效的 Bearer API Key",
            reason="missing_api_key",
        )

    key_record = _load_api_key_record_for_usage(db, raw_api_key)
    if not key_record:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="API Key 无效",
            reason="invalid_api_key",
        )

    if not key_record.is_active:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="API Key 已禁用",
            reason="disabled_api_key",
        )

    if key_record.is_locked and not key_record.is_standalone:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="API Key 已锁定",
            reason="locked_api_key",
        )

    expires_at = _normalize_utc(key_record.expires_at)
    if expires_at and expires_at < datetime.now(timezone.utc):
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="API Key 已过期",
            reason="expired_api_key",
        )

    user = key_record.user
    if user is None or not user.is_active:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="用户已禁用",
            reason="inactive_user",
        )

    if user.is_deleted:
        return _build_usage_payload(
            is_active=False,
            is_valid=False,
            quota_exhausted=False,
            remaining=None,
            message="用户已删除",
            reason="deleted_user",
        )

    balance_result = UsageQueryMixin.check_request_balance_details(db, user, api_key=key_record)
    if not balance_result.allowed:
        reason = "wallet_unavailable" if "钱包不可用" in balance_result.message else "quota_exhausted"
        return _build_usage_payload(
            is_active=False,
            is_valid=True,
            quota_exhausted=True,
            remaining=balance_result.remaining,
            message=balance_result.message,
            reason=reason,
        )

    return _build_usage_payload(
        is_active=True,
        is_valid=True,
        quota_exhausted=False,
        remaining=balance_result.remaining,
        message="OK",
        reason="active",
    )


@router.get("/v1/usage")
def get_usage_status(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Any:
    """返回 API Key 的余额与可用状态，不更新 last_used_at。"""
    return _get_usage_status(db, _extract_bearer_token(authorization))
