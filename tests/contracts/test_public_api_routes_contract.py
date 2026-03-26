from __future__ import annotations

from fastapi import FastAPI


def _build_contract_app() -> FastAPI:
    from src.api.public.claude import router as claude_router
    from src.api.public.gemini import router as gemini_router
    from src.api.public.openai import router as openai_router
    from src.api.public.usage import router as usage_router

    app = FastAPI()
    app.include_router(claude_router)
    app.include_router(openai_router)
    app.include_router(gemini_router)
    app.include_router(usage_router)
    return app


def test_public_api_routes_contract_paths_and_tags() -> None:
    app = _build_contract_app()
    schema = app.openapi()

    paths = schema.get("paths") or {}

    expected = [
        ("/v1/messages", "post", "Claude API"),
        ("/v1/messages/count_tokens", "post", "Claude API"),
        ("/v1/chat/completions", "post", "OpenAI API"),
        ("/v1/responses", "post", "OpenAI API"),
        ("/v1/usage", "get", "System Catalog"),
        ("/v1beta/models/{model}:generateContent", "post", "Gemini API"),
        ("/v1beta/models/{model}:streamGenerateContent", "post", "Gemini API"),
        ("/v1/models/{model}:generateContent", "post", "Gemini API"),
        ("/v1/models/{model}:streamGenerateContent", "post", "Gemini API"),
    ]

    for path, method, expected_tag in expected:
        assert path in paths, f"missing path {path}"
        operations = paths.get(path) or {}
        assert method in operations, f"missing {method.upper()} {path}"
        tags = operations.get(method, {}).get("tags") or []
        assert expected_tag in tags, f"{method.upper()} {path} missing tag {expected_tag}"
