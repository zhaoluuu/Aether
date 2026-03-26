from __future__ import annotations

from src.models.database import Model
from src.services.model.provider_model_mapping import apply_provider_model_request_overrides


def test_select_provider_model_mapping_preserves_request_overrides() -> None:
    model = Model(
        provider_model_name="gpt-5.3-codex",
        provider_model_mappings=[
            {
                "name": "gpt-5.2-codex",
                "priority": 1,
                "api_formats": ["openai:cli"],
                "request_overrides": {
                    "reasoning_effort_map": {
                        "*": "medium",
                        "high": "medium",
                    }
                },
            }
        ],
    )

    selected = model.select_provider_model_mapping(
        affinity_key="user-key-1",
        api_format="openai:cli",
    )

    assert selected is not None
    assert selected["name"] == "gpt-5.2-codex"
    assert selected["request_overrides"] == {
        "reasoning_effort_map": {
            "*": "medium",
            "high": "medium",
        }
    }


def test_select_provider_model_mapping_filters_by_api_format() -> None:
    model = Model(
        provider_model_name="gpt-5.3-codex",
        provider_model_mappings=[
            {
                "name": "gpt-5.2-codex",
                "priority": 1,
                "api_formats": ["openai:cli"],
            }
        ],
    )

    selected = model.select_provider_model_mapping(api_format="openai:chat")

    assert selected is None
    assert model.select_provider_model_name(api_format="openai:chat") == "gpt-5.3-codex"


def test_apply_provider_model_request_overrides_prefers_exact_match() -> None:
    request_body = {
        "model": "gpt-5.2-codex",
        "reasoning": {
            "effort": "high",
        },
    }

    result = apply_provider_model_request_overrides(
        request_body,
        {
            "name": "gpt-5.2-codex",
            "request_overrides": {
                "reasoning_effort_map": {
                    "*": "medium",
                    "high": "low",
                }
            },
        },
        provider_api_format="openai:cli",
    )

    assert result["reasoning"]["effort"] == "low"


def test_apply_provider_model_request_overrides_uses_wildcard() -> None:
    request_body = {
        "reasoning": {
            "effort": "xhigh",
        },
    }

    result = apply_provider_model_request_overrides(
        request_body,
        {
            "name": "gpt-5.2-codex",
            "request_overrides": {
                "reasoning_effort_map": {
                    "*": "medium",
                }
            },
        },
        provider_api_format="openai:cli",
    )

    assert result["reasoning"]["effort"] == "medium"


def test_apply_provider_model_request_overrides_skips_missing_effort() -> None:
    request_body = {
        "reasoning": {},
    }

    result = apply_provider_model_request_overrides(
        request_body,
        {
            "name": "gpt-5.2-codex",
            "request_overrides": {
                "reasoning_effort_map": {
                    "*": "medium",
                }
            },
        },
        provider_api_format="openai:cli",
    )

    assert result["reasoning"] == {}


def test_apply_provider_model_request_overrides_rewrites_openai_chat_semantically() -> None:
    request_body = {
        "reasoning_effort": "high",
    }

    result = apply_provider_model_request_overrides(
        request_body,
        {
            "name": "gpt-5.2-codex",
            "request_overrides": {
                "reasoning_effort_map": {
                    "*": "medium",
                }
            },
        },
        provider_api_format="openai:chat",
    )

    assert result["reasoning_effort"] == "medium"
    assert "reasoning" not in result


def test_apply_provider_model_request_overrides_rewrites_claude_semantically() -> None:
    request_body = {
        "output_config": {
            "effort": "max",
        },
    }

    result = apply_provider_model_request_overrides(
        request_body,
        {
            "name": "claude-sonnet",
            "request_overrides": {
                "reasoning_effort_map": {
                    "xhigh": "medium",
                }
            },
        },
        provider_api_format="claude:messages",
    )

    assert result["output_config"]["effort"] == "medium"
    assert "reasoning" not in result
