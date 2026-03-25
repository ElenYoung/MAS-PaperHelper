from __future__ import annotations

import json
import os

import httpx

from core.config import GlobalConfig, UserConfig


class LLMClient:
    def __init__(self, global_config: GlobalConfig, user: UserConfig) -> None:
        self.global_config = global_config
        self.user = user

    def generate_summary(self, prompt: str) -> dict[str, str] | None:
        provider = self.global_config.llm_provider.lower().strip()
        if provider == "ollama":
            return self._call_ollama(prompt)
        if provider in {"openai", "openai_compatible"}:
            return self._call_openai_compatible(prompt)
        return None

    def _call_ollama(self, prompt: str) -> dict[str, str] | None:
        base = (
            self.global_config.base_model_api_base
            or self.global_config.llm_api_base
            or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        url = f"{base.rstrip('/')}/api/generate"
        payload = {
            "model": self.global_config.base_model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                text = response.json().get("response", "").strip()
            return _parse_json_payload(text)
        except Exception:
            return None

    def _call_openai_compatible(self, prompt: str) -> dict[str, str] | None:
        base = (
            self.global_config.base_model_api_base
            or self.global_config.llm_api_base
            or "https://api.openai.com"
        )
        api_key = self._resolve_api_key()

        url = f"{base.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.global_config.base_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return strict JSON with keys: research_problem, innovation_summary.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                text = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
            return _parse_json_payload(text)
        except Exception:
            return None

    def _resolve_api_key(self) -> str | None:
        if self.user.llm_api_key:
            return self.user.llm_api_key

        env_name = (self.global_config.llm_api_key_env or "").strip()
        if not env_name or env_name.upper() in {"EMPTY", "NONE", "NULL"}:
            return ""

        value = os.getenv(env_name)
        if value is None:
            return None
        return value


def _parse_json_payload(text: str) -> dict[str, str] | None:
    if not text:
        return None
    normalized = text.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        if normalized.startswith("json"):
            normalized = normalized[4:].strip()
    try:
        data = json.loads(normalized)
    except Exception:
        return None

    keys = {"research_problem", "innovation_summary"}
    if not keys.issubset(data.keys()):
        return None
    return {
        "research_problem": str(data["research_problem"]),
        "innovation_summary": str(data["innovation_summary"]),
    }
