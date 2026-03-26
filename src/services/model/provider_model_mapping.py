"""Provider 模型映射扩展能力。"""

from __future__ import annotations

from typing import Any

from src.core.api_format.conversion.field_mappings import REASONING_EFFORT_TO_CLAUDE_EFFORT
from src.core.logger import logger


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
    if not isinstance(reasoning_effort_map, dict) or not reasoning_effort_map:
        return request_body

    current_effort = _extract_semantic_reasoning_effort(request_body)
    if not isinstance(current_effort, str) or not current_effort.strip():
        return request_body

    normalized_current_effort = current_effort.strip().lower()
    target_effort = reasoning_effort_map.get(normalized_current_effort)
    if not isinstance(target_effort, str) or not target_effort.strip():
        wildcard_effort = reasoning_effort_map.get("*")
        target_effort = wildcard_effort if isinstance(wildcard_effort, str) else None

    if not isinstance(target_effort, str) or not target_effort.strip():
        return request_body

    normalized_target_effort = target_effort.strip().lower()
    if normalized_target_effort == normalized_current_effort:
        return request_body

    _write_semantic_reasoning_effort(
        request_body,
        normalized_target_effort,
        provider_api_format,
    )
    logger.debug(
        "[provider_model_mapping] rewritten reasoning_effort: {} -> {} for mapped model {} (api_format={})",
        normalized_current_effort,
        normalized_target_effort,
        selected_mapping.get("name") or "<unknown>",
        provider_api_format or "<unknown>",
    )
    return request_body
