from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


class SourceConfig(BaseModel):
    enabled: bool = True
    priority: int = 100
    rate_limit_per_min: int = 10
    timeout_seconds: int = 20
    retry: int = 2


class RankingWeights(BaseModel):
    recency: float = 0.5
    relevance: float = 0.5


class UserConfig(BaseModel):
    user_id: str
    interests: list[str] = Field(default_factory=list)
    search_query: str
    update_frequency: str = "daily"
    enabled_sources: list[str] = Field(default_factory=list)
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)
    llm_api_key: str | None = None


class GlobalConfig(BaseModel):
    llm_provider: str = "ollama"
    base_model: str = "qwen2.5-72b-instruct"
    embedding_model: str = "text-embedding-3-small"
    base_model_api_base: str | None = None
    embedding_api_base: str | None = None
    max_concurrent_tasks: int = 3
    ranking_threshold: float = 6.0
    min_relevance_ratio: float = 0.2
    recency_window_days: int = 60
    summary_language: Literal["zh", "en"] = "en"
    summary_max_chars: int = 1000
    summary_limit: int = 3
    discovery_limit_per_source: int = 10
    use_llm_summary: bool = False
    llm_api_base: str | None = None
    llm_api_key_env: str = "OPENAI_API_KEY"
    parser_backend: str = "marker"
    parser_max_pages: int = 8
    parser_device: str = "cuda"
    use_cross_encoder: bool = False
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    auto_query_from_interests: bool = True
    auto_query_mode: Literal["manual", "interests", "merge"] = "merge"
    source_query_templates: dict[str, str] = Field(default_factory=dict)
    keyword_kb_enabled: bool = True
    keyword_kb_path: str = "data/keyword_kb.json"
    keyword_expand_limit: int = 10
    keyword_max_new_terms_per_run: int = 20
    keyword_whitelist: list[str] = Field(default_factory=list)
    keyword_blacklist: list[str] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    backend: str = "sqlite"
    sqlite_path: str = "data/app.db"
    clickhouse_dsn: str | None = None


class VectorStoreConfig(BaseModel):
    backend: str = "none"
    chroma_path: str = "data/vector_db"


class AppConfig(BaseModel):
    global_config: GlobalConfig = Field(alias="global")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    sources: dict[str, SourceConfig]
    users: list[UserConfig]


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _coerce_scalar(text: str) -> object:
    lowered = text.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", text.strip()):
        try:
            return int(text.strip())
        except ValueError:
            return text
    if re.fullmatch(r"[+-]?\d+\.\d+", text.strip()):
        try:
            return float(text.strip())
        except ValueError:
            return text
    return text


def _expand_env_string(value: str) -> object:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2) if match.group(2) is not None else ""
        return os.getenv(name, default)

    expanded = _ENV_PATTERN.sub(repl, value)
    # If the whole string is env-resolved scalar text, coerce it to bool/int/float/None.
    if _ENV_PATTERN.search(value):
        return _coerce_scalar(expanded)
    return expanded


def _expand_env_in_value(value: object) -> object:
    if isinstance(value, dict):
        return {k: _expand_env_in_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_in_value(item) for item in value]
    if isinstance(value, str):
        return _expand_env_string(value)
    return value


def _is_env_placeholder(value: object) -> bool:
    return isinstance(value, str) and bool(_ENV_PATTERN.fullmatch(value.strip()))


def _preserve_env_placeholders(new_value: object, old_value: object) -> object:
    if _is_env_placeholder(old_value) and isinstance(new_value, (str, int, float, bool)):
        return old_value
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        merged: dict = {}
        for key, val in new_value.items():
            merged[key] = _preserve_env_placeholders(val, old_value.get(key))
        return merged
    if isinstance(new_value, list) and isinstance(old_value, list):
        # Keep list shape from new config; preserve per-index placeholders when present.
        merged_list: list = []
        for idx, val in enumerate(new_value):
            old_item = old_value[idx] if idx < len(old_value) else None
            merged_list.append(_preserve_env_placeholders(val, old_item))
        return merged_list
    return new_value


def load_config(config_path: str | Path = "config/config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    _load_dotenv(path.parent.parent / ".env")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    raw = _expand_env_in_value(raw)

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid config format: {exc}") from exc


def save_config(app_config: AppConfig, config_path: str | Path = "config/config.yaml") -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = app_config.model_dump(by_alias=True)

    existing_raw: dict | None = None
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                existing_raw = loaded

    if existing_raw is not None:
        payload = _preserve_env_placeholders(payload, existing_raw)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def get_user_config(app_config: AppConfig, user_id: str) -> UserConfig:
    for user in app_config.users:
        if user.user_id == user_id:
            return user
    raise ValueError(f"Unknown user_id: {user_id}")
