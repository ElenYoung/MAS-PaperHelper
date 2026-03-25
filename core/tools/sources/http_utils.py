from __future__ import annotations

import random
import time

import httpx

from core.tools.sources.errors import SourceFetchError


def get_json_with_retry(
    url: str,
    params: dict[str, str],
    timeout_seconds: int,
    retry: int,
    source_name: str,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(retry + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # pragma: no cover - network behavior
            last_error = exc
            if attempt < retry:
                sleep_seconds = (attempt + 1) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)

    raise SourceFetchError(f"{source_name} request failed: {last_error}")


def get_text_with_retry(
    url: str,
    params: dict[str, str],
    timeout_seconds: int,
    retry: int,
    source_name: str,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retry + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.text
        except Exception as exc:  # pragma: no cover - network behavior
            last_error = exc
            if attempt < retry:
                sleep_seconds = (attempt + 1) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)

    raise SourceFetchError(f"{source_name} request failed: {last_error}")
