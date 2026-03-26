from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.models.database import ApiKey, GlobalModel, Model, Provider, ProviderAPIKey
from src.services.model.global_model import GlobalModelService


def test_auto_disassociate_short_circuits_when_unlimited_key_exists() -> None:
    db = MagicMock()
    provider_query = MagicMock()
    provider_query.filter.return_value.first.return_value = SimpleNamespace(name="Provider A")

    unlimited_query = MagicMock()
    unlimited_query.filter.return_value.limit.return_value.first.return_value = object()

    def _query(*entities: object) -> MagicMock:
        entity = entities[0]
        if entity is Provider:
            return provider_query
        if entity is ProviderAPIKey.id:
            return unlimited_query
        if entity is Model:
            raise AssertionError("model query should not run when unlimited key exists")
        raise AssertionError(f"unexpected query: {entities}")

    db.query.side_effect = _query

    result = GlobalModelService.auto_disassociate_provider_by_key_whitelist(db, "provider-1")

    assert result == {"success": [], "errors": []}
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_auto_disassociate_deletes_unmatched_auto_associated_models(
    monkeypatch,
) -> None:
    db = MagicMock()
    provider_query = MagicMock()
    provider_query.filter.return_value.first.return_value = SimpleNamespace(name="Provider B")

    unlimited_query = MagicMock()
    unlimited_query.filter.return_value.limit.return_value.first.return_value = None

    allowed_models_query = MagicMock()
    # db.query(ProviderAPIKey.allowed_models).all() returns list of tuples
    allowed_models_query.filter.return_value.all.return_value = [
        (["gpt-4o"],),
        ([],),
    ]

    model = SimpleNamespace(
        id="model-1",
        global_model=SimpleNamespace(
            id="gm-1",
            name="claude-sonnet",
            config={"model_mappings": ["claude-*"]},
        ),
    )
    models_query = MagicMock()
    models_query.options.return_value.filter.return_value.all.return_value = [model]

    def _query(*entities: object) -> MagicMock:
        entity = entities[0]
        if entity is Provider:
            return provider_query
        if entity is ProviderAPIKey.id:
            return unlimited_query
        if entity is ProviderAPIKey.allowed_models:
            return allowed_models_query
        if entity is Model:
            return models_query
        raise AssertionError(f"unexpected query: {entities}")

    db.query.side_effect = _query
    monkeypatch.setattr(
        "src.core.model_permissions.match_model_with_pattern",
        lambda pattern, allowed_model: pattern == allowed_model,
    )

    result = GlobalModelService.auto_disassociate_provider_by_key_whitelist(db, "provider-2")

    assert result["errors"] == []
    assert result["success"] == [
        {
            "model_id": "model-1",
            "global_model_id": "gm-1",
            "global_model_name": "claude-sonnet",
        }
    ]
    db.delete.assert_called_once_with(model)
    db.commit.assert_called_once()


def test_delete_global_model_removes_model_from_api_key_allowed_models() -> None:
    db = MagicMock()
    global_model = SimpleNamespace(id="gm-1", name="gpt-4o")
    kept_key = SimpleNamespace(id="key-1", allowed_models=["claude-3-7-sonnet"])
    trimmed_key = SimpleNamespace(id="key-2", allowed_models=["gpt-4o", "gpt-4o-mini"])
    emptied_key = SimpleNamespace(id="key-3", allowed_models=["gpt-4o"])

    global_model_query = MagicMock()
    global_model_query.filter.return_value.first.return_value = global_model

    api_key_query = MagicMock()
    api_key_query.filter.return_value.all.return_value = [kept_key, trimmed_key, emptied_key]

    count_query = MagicMock()
    count_query.filter.return_value.scalar.return_value = 0

    def _query(*entities: object) -> MagicMock:
        entity = entities[0]
        if entity is GlobalModel:
            return global_model_query
        if entity is ApiKey:
            return api_key_query
        return count_query

    db.query.side_effect = _query

    GlobalModelService.delete_global_model(db, "gm-1")

    assert kept_key.allowed_models == ["claude-3-7-sonnet"]
    assert trimmed_key.allowed_models == ["gpt-4o-mini"]
    assert emptied_key.allowed_models == []
    db.delete.assert_called_once_with(global_model)
    db.commit.assert_called_once()
