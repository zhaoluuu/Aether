"""Provider 模型映射扩展能力。"""

from __future__ import annotations

from typing import Any

from src.core.api_format.conversion.field_mappings import REASONING_EFFORT_TO_CLAUDE_EFFORT
from src.core.logger import logger


def _resolve_mapped_value(
    current_value: str | None,
    value_map: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not isinstance(current_value, str) or not current_value.strip():
        return None, None
    if not isinstance(value_map, dict) or not value_map:
        return None, None

    normalized_current_value = current_value.strip().lower()
    target_value = value_map.get(normalized_current_value)
    if not isinstance(target_value, str) or not target_value.strip():
        wildcard_value = value_map.get("*")
        target_value = wildcard_value if isinstance(wildcard_value, str) else None

    if not isinstance(target_value, str) or not target_value.strip():
        return normalized_current_value, None

    normalized_target_value = target_value.strip().lower()
    if normalized_target_value == normalized_current_value:
        return normalized_current_value, None

    return normalized_current_value, normalized_target_value


def _extract_semantic_reasoning_effort(request_body: dict[str, Any]) -> str | None:
    reasoning = request_body.get("reasoning")
    if isinstance(reasoning, dict):
        effort = reasoning.get("effort")
        if isinstance(effort, str) and effort.strip():
            return effort.strip().lower()

    reasoning_effort = request_body.get("reasoning_effort")
    if isinstance(reasoning_effort, str) and reasoning_effort.strip():
        return reasoning_effort.strip().lower()

    output_config = request_body.get("output_config")
    if isinstance(output_config, dict):
        effort = output_config.get("effort")
        if isinstance(effort, str) and effort.strip():
            normalized_effort = effort.strip().lower()
            for semantic_effort, claude_effort in REASONING_EFFORT_TO_CLAUDE_EFFORT.items():
                if claude_effort == normalized_effort:
                    return semantic_effort
            return normalized_effort

    return None


def _write_semantic_reasoning_effort(
    request_body: dict[str, Any],
    target_effort: str,
    provider_api_format: str | None,
) -> dict[str, Any]:
    normalized_api_format = str(provider_api_format or "").strip().lower()

    if normalized_api_format.startswith("claude:"):
        output_config = request_body.get("output_config")
        if not isinstance(output_config, dict):
            output_config = {}
            request_body["output_config"] = output_config
        output_config["effort"] = REASONING_EFFORT_TO_CLAUDE_EFFORT.get(target_effort, target_effort)
        request_body.pop("reasoning_effort", None)
        request_body.pop("reasoning", None)
        return request_body

    if normalized_api_format == "openai:chat":
        request_body["reasoning_effort"] = target_effort
        request_body.pop("reasoning", None)
        output_config = request_body.get("output_config")
        if isinstance(output_config, dict):
            output_config.pop("effort", None)
            if not output_config:
                request_body.pop("output_config", None)
        return request_body

    if normalized_api_format == "openai:cli":
        reasoning = request_body.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
            request_body["reasoning"] = reasoning
        reasoning["effort"] = target_effort
        request_body.pop("reasoning_effort", None)
        output_config = request_body.get("output_config")
        if isinstance(output_config, dict):
            output_config.pop("effort", None)
            if not output_config:
                request_body.pop("output_config", None)
        return request_body

    # 回退策略：尽量保留原请求已有的字段形态
    if isinstance(request_body.get("reasoning"), dict):
        request_body["reasoning"]["effort"] = target_effort
        return request_body
    if "reasoning_effort" in request_body:
        request_body["reasoning_effort"] = target_effort
        return request_body
    if isinstance(request_body.get("output_config"), dict):
        request_body["output_config"]["effort"] = REASONING_EFFORT_TO_CLAUDE_EFFORT.get(
            target_effort,
            target_effort,
        )
        return request_body

    reasoning = {}
    reasoning["effort"] = target_effort
    request_body["reasoning"] = reasoning
    return request_body


def _extract_semantic_verbosity(request_body: dict[str, Any]) -> str | None:
    text_config = request_body.get("text")
    if isinstance(text_config, dict):
        verbosity = text_config.get("verbosity")
        if isinstance(verbosity, str) and verbosity.strip():
            return verbosity.strip().lower()

    verbosity = request_body.get("verbosity")
    if isinstance(verbosity, str) and verbosity.strip():
        return verbosity.strip().lower()

    return None


def _write_semantic_verbosity(
    request_body: dict[str, Any],
    target_verbosity: str,
    provider_api_format: str | None,
) -> dict[str, Any]:
    normalized_api_format = str(provider_api_format or "").strip().lower()

    if normalized_api_format == "openai:cli":
        text_config = request_body.get("text")
        if not isinstance(text_config, dict):
            text_config = {}
            request_body["text"] = text_config
        text_config["verbosity"] = target_verbosity
        request_body.pop("verbosity", None)
        return request_body

    if normalized_api_format == "openai:chat":
        request_body["verbosity"] = target_verbosity
        text_config = request_body.get("text")
        if isinstance(text_config, dict):
            text_config.pop("verbosity", None)
            if not text_config:
                request_body.pop("text", None)
        return request_body

    if isinstance(request_body.get("text"), dict):
        request_body["text"]["verbosity"] = target_verbosity
        return request_body
    if "verbosity" in request_body:
        request_body["verbosity"] = target_verbosity
        return request_body

    request_body["verbosity"] = target_verbosity
    return request_body


def apply_provider_model_request_overrides(
    request_body: dict[str, Any],
    selected_mapping: dict[str, Any] | None,
    *,
    provider_api_format: str | None = None,
) -> dict[str, Any]:
    """按映射配置调整发往上游的请求体。"""
    if not selected_mapping:
        return request_body

    request_overrides = selected_mapping.get("request_overrides")
    if not isinstance(request_overrides, dict):
        return request_body

    reasoning_effort_map = request_overrides.get("reasoning_effort_map")
    current_effort, target_effort = _resolve_mapped_value(
        _extract_semantic_reasoning_effort(request_body),
        reasoning_effort_map if isinstance(reasoning_effort_map, dict) else None,
    )
    if current_effort and target_effort:
        _write_semantic_reasoning_effort(
            request_body,
            target_effort,
            provider_api_format,
        )
        logger.debug(
            "[provider_model_mapping] rewritten reasoning_effort: {} -> {} for mapped model {} (api_format={})",
            current_effort,
            target_effort,
            selected_mapping.get("name") or "<unknown>",
            provider_api_format or "<unknown>",
        )

    verbosity_map = request_overrides.get("verbosity_map")
    current_verbosity, target_verbosity = _resolve_mapped_value(
        _extract_semantic_verbosity(request_body),
        verbosity_map if isinstance(verbosity_map, dict) else None,
    )
    if current_verbosity and target_verbosity:
        _write_semantic_verbosity(
            request_body,
            target_verbosity,
            provider_api_format,
        )
        logger.debug(
            "[provider_model_mapping] rewritten verbosity: {} -> {} for mapped model {} (api_format={})",
            current_verbosity,
            target_verbosity,
            selected_mapping.get("name") or "<unknown>",
            provider_api_format or "<unknown>",
        )

    return request_body
