from __future__ import annotations

from typing import Any

import httpx

from core.config import AppConfig


def run_diagnostics(app_config: AppConfig) -> dict[str, Any]:
    generation_base = (
        app_config.global_config.base_model_api_base
        or app_config.global_config.llm_api_base
        or ""
    )
    embedding_base = app_config.global_config.embedding_api_base or generation_base

    checks = {
        "generation_endpoint": _check_openai_compatible_models(generation_base),
        "embedding_endpoint": _check_openai_compatible_models(embedding_base),
        "sources": {
            name: {"enabled": cfg.enabled, "priority": cfg.priority}
            for name, cfg in app_config.sources.items()
        },
        "users": [u.user_id for u in app_config.users],
    }

    checks["overall_ok"] = bool(
        checks["generation_endpoint"]["ok"] and checks["embedding_endpoint"]["ok"]
    )
    return checks


def _check_openai_compatible_models(base_url: str) -> dict[str, Any]:
    if not base_url:
        return {"ok": False, "reason": "missing base url"}

    url = f"{base_url.rstrip('/')}/models"
    try:
        with httpx.Client(timeout=6) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
        return {
            "ok": True,
            "url": url,
            "models_count": len(data.get("data", [])) if isinstance(data, dict) else None,
        }
    except Exception as exc:
        return {"ok": False, "url": url, "reason": str(exc)}
