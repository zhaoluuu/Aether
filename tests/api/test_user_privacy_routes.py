from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth.routes import AuthCurrentUserAdapter
from src.api.public.catalog import router as public_catalog_router
from src.api.public.models import (
    _build_openai_list_response,
    _build_openai_model_response,
)
from src.api.public.system_catalog import router as public_system_router
from src.api.public.usage import router as public_usage_router
from src.api.base.models_service import sanitize_public_global_model_config
from src.api.user_me.routes import GetPreferencesAdapter
from src.api.user_me.routes import router as me_router
from src.api.base.models_service import ModelInfo
from src.database import get_db
from src.services.user.preference import PreferenceService


@pytest.mark.asyncio
async def test_auth_current_user_adapter_omits_access_restriction_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.api.auth.routes.WalletService.get_wallet", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "src.api.auth.routes.WalletService.serialize_wallet_summary",
        lambda _wallet: {"balance": 0},
    )

    adapter = AuthCurrentUserAdapter()
    context = SimpleNamespace(
        db=SimpleNamespace(),
        user=SimpleNamespace(
            id="user-1",
            email="u@example.com",
            username="NyaDoo",
            role=SimpleNamespace(value="user"),
            is_active=True,
            created_at=datetime(2026, 3, 19, 12, 0, 0),
            last_login_at=None,
            auth_source=SimpleNamespace(value="local"),
            allowed_providers=["provider-a"],
            allowed_api_formats=["openai:chat"],
            allowed_models=["gpt-5.1"],
        ),
        request=SimpleNamespace(state=SimpleNamespace()),
    )

    result = await adapter.handle(context)

    assert "allowed_providers" not in result
    assert "allowed_api_formats" not in result
    assert "allowed_models" not in result


@pytest.mark.asyncio
async def test_get_preferences_adapter_omits_default_provider_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.api.user_me.routes.PreferenceService.get_or_create_preferences",
        lambda *_args, **_kwargs: SimpleNamespace(
            avatar_url="https://example.com/avatar.png",
            bio="hello",
            default_provider_id="provider-1",
            default_provider=SimpleNamespace(name="openai"),
            theme="light",
            language="zh-CN",
            timezone="Asia/Shanghai",
            email_notifications=True,
            usage_alerts=True,
            announcement_notifications=False,
        ),
    )

    adapter = GetPreferencesAdapter()
    context = SimpleNamespace(
        db=SimpleNamespace(),
        user=SimpleNamespace(id="user-1"),
        request=SimpleNamespace(state=SimpleNamespace()),
    )

    result = await adapter.handle(context)

    assert "default_provider_id" not in result
    assert "default_provider" not in result


def test_preference_service_profile_omits_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id="user-1",
        email="u@example.com",
        username="NyaDoo",
        role=SimpleNamespace(value="user"),
        is_active=True,
        created_at=datetime(2026, 3, 19, 12, 0, 0),
        last_login_at=None,
        auth_source=SimpleNamespace(value="local"),
        password_hash="hashed",
        api_keys=[SimpleNamespace(id="key-1")],
    )
    monkeypatch.setattr(
        PreferenceService,
        "get_or_create_preferences",
        staticmethod(
            lambda *_args, **_kwargs: SimpleNamespace(
                avatar_url=None,
                bio=None,
                default_provider_id="provider-1",
                default_provider=SimpleNamespace(name="openai"),
                theme="light",
                language="zh-CN",
                timezone="Asia/Shanghai",
                email_notifications=True,
                usage_alerts=True,
                announcement_notifications=True,
            )
        ),
    )
    monkeypatch.setattr("src.services.user.preference.WalletService.get_wallet", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "src.services.user.preference.WalletService.serialize_wallet_summary",
        lambda _wallet: {"total_consumed": 0},
    )

    result = PreferenceService.get_user_with_preferences(db, "user-1")

    assert "default_provider" not in result["preferences"]
    assert "stats" not in result


def test_hidden_user_and_public_provider_routes_return_404() -> None:
    app = FastAPI()
    app.include_router(me_router)
    app.include_router(public_catalog_router)
    app.include_router(public_system_router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)

    assert client.get("/api/users/me/providers").status_code == 404
    assert client.put("/api/users/me/api-keys/key-1/providers", json={"allowed_providers": []}).status_code == 404
    assert client.get("/api/public/providers").status_code == 404
    assert client.get("/v1/providers").status_code == 404
    assert client.get("/v1/providers/provider-a").status_code == 404
    assert client.get("/v1/test-connection").status_code == 404

    root_payload = client.get("/").json()
    assert "current_provider" not in root_payload
    assert "available_providers" not in root_payload
    assert "providers" not in root_payload["endpoints"]
    assert "test_connection" not in root_payload["endpoints"]


def test_public_usage_missing_bearer_returns_inactive_payload() -> None:
    app = FastAPI()
    app.include_router(public_usage_router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)

    response = client.get("/v1/usage")

    assert response.status_code == 200
    assert response.json() == {
        "status": "missing_api_key",
        "reason": "missing_api_key",
        "is_active": False,
        "is_valid": False,
        "quota_exhausted": False,
        "remaining": None,
        "balance": None,
        "unit": "USD",
        "message": "未提供有效的 Bearer API Key",
    }


def test_public_usage_reports_quota_exhausted_without_touching_auth_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(public_usage_router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)

    key_record = SimpleNamespace(
        is_active=True,
        is_locked=False,
        is_standalone=False,
        expires_at=None,
        user=SimpleNamespace(is_active=True, is_deleted=False),
    )
    monkeypatch.setattr(
        "src.api.public.usage._load_api_key_record_for_usage",
        lambda _db, _raw_api_key: key_record,
    )
    monkeypatch.setattr(
        "src.api.public.usage.UsageQueryMixin.check_request_balance_details",
        lambda _db, _user, estimated_tokens=0, estimated_cost=0, api_key=None: SimpleNamespace(
            allowed=False,
            message="余额不足（剩余: $0.00）",
            remaining=0.0,
        ),
    )

    response = client.get("/v1/usage", headers={"Authorization": "Bearer sk-test"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "quota_exhausted",
        "reason": "quota_exhausted",
        "is_active": False,
        "is_valid": True,
        "quota_exhausted": True,
        "remaining": 0.0,
        "balance": 0.0,
        "unit": "USD",
        "message": "余额不足（剩余: $0.00）",
    }


def test_public_openai_model_responses_use_gateway_owner() -> None:
    model = ModelInfo(
        id="gpt-5.1",
        display_name="GPT-5.1",
        description=None,
        created_at="2026-03-19T12:00:00Z",
        created_timestamp=1742385600,
        provider_name="openai",
    )

    list_payload = _build_openai_list_response([model])
    detail_payload = _build_openai_model_response(model)

    assert list_payload["data"][0]["owned_by"] == "aether"
    assert detail_payload["owned_by"] == "aether"


def test_public_global_model_config_omits_internal_mapping_rules() -> None:
    sanitized = sanitize_public_global_model_config(
        {
            "description": "Fast model",
            "streaming": True,
            "vision": False,
            "model_mappings": ["gpt-4o-.*"],
            "billing": {"video": {"price_per_second_by_resolution": {"720p": 0.1}}},
        }
    )

    assert sanitized == {
        "description": "Fast model",
        "streaming": True,
        "vision": False,
    }
