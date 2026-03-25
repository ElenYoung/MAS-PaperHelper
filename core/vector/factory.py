from __future__ import annotations

from core.config import AppConfig
from core.vector.chroma_store import ChromaStore


def create_vector_store(app_config: AppConfig) -> ChromaStore | None:
    backend = app_config.vector_store.backend.lower()
    if backend == "chroma":
        return ChromaStore(
            persist_path=app_config.vector_store.chroma_path,
            embedding_model=app_config.global_config.embedding_model,
            embedding_api_base=app_config.global_config.embedding_api_base,
            embedding_api_key_env=app_config.global_config.llm_api_key_env,
        )
    return None
