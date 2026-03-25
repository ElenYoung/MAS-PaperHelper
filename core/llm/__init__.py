from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import GlobalConfig, UserConfig


@dataclass
class LLMResponse:
    """Simple LLM response wrapper."""

    content: str


class SimpleLLM:
    """Simple LLM interface for intelligent search agents."""

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        global_config: GlobalConfig | None = None,
        user_config: UserConfig | None = None,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.global_config = global_config
        self.user_config = user_config

    def complete(self, prompt: str) -> LLMResponse:
        """Complete a prompt and return the response."""
        import json
        import os

        import httpx

        # Determine provider and config
        provider = "openai_compatible"
        base_url = self.api_base
        model_name = self.model
        api_key = os.getenv("OPENAI_API_KEY", "")

        if self.global_config:
            provider = self.global_config.llm_provider.lower().strip()
            base_url = base_url or self.global_config.base_model_api_base or self.global_config.llm_api_base
            model_name = model_name or self.global_config.base_model

            # Resolve API key
            env_name = (self.global_config.llm_api_key_env or "").strip()
            if env_name and env_name.upper() not in {"EMPTY", "NONE", "NULL"}:
                api_key = os.getenv(env_name, api_key)

            if self.user_config and self.user_config.llm_api_key:
                api_key = self.user_config.llm_api_key

        # Default values
        base_url = base_url or "http://127.0.0.1:8000/v1"
        model_name = model_name or "Qwen/Qwen3-Next-80B-A3B-Instruct"

        try:
            if provider == "ollama":
                # Ollama API
                ollama_base = base_url.replace("/v1", "")
                url = f"{ollama_base.rstrip('/')}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                }
                with httpx.Client(timeout=120) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    content = response.json().get("response", "").strip()
            else:
                # OpenAI compatible API
                url = f"{base_url.rstrip('/')}/chat/completions"
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                with httpx.Client(timeout=120) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )

            return LLMResponse(content=content)

        except Exception as e:
            # Return empty response on error
            return LLMResponse(content=f"Error: {e}")


def get_llm(
    model: str | None = None,
    api_base: str | None = None,
    global_config: GlobalConfig | None = None,
    user_config: UserConfig | None = None,
) -> SimpleLLM:
    """Get a simple LLM interface for making completions."""
    return SimpleLLM(
        model=model,
        api_base=api_base,
        global_config=global_config,
        user_config=user_config,
    )
