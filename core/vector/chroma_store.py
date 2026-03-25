from __future__ import annotations

import os

from core.models import PaperSummary


class ChromaStore:
    def __init__(
        self,
        persist_path: str = "data/vector_db",
        embedding_model: str | None = None,
        embedding_api_base: str | None = None,
        embedding_api_key_env: str | None = None,
    ) -> None:
        self.persist_path = persist_path
        self.embedding_model = embedding_model
        self.embedding_api_base = embedding_api_base
        self.embedding_api_key_env = embedding_api_key_env or "OPENAI_API_KEY"

    def upsert_summaries(self, user_id: str, summaries: list[PaperSummary]) -> None:
        try:
            import chromadb  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("chromadb is required for ChromaStore") from exc

        client = chromadb.PersistentClient(path=self.persist_path)
        collection_kwargs: dict = {"name": f"papers_{user_id}"}

        if self.embedding_model and self.embedding_api_base:
            try:
                from chromadb.utils import embedding_functions  # type: ignore

                api_key = os.getenv(self.embedding_api_key_env, "")
                collection_kwargs["embedding_function"] = embedding_functions.OpenAIEmbeddingFunction(
                    model_name=self.embedding_model,
                    api_base=self.embedding_api_base,
                    api_key=api_key,
                )
            except Exception:
                # If custom embedding wiring fails, fall back to default local behavior.
                pass

        collection = client.get_or_create_collection(**collection_kwargs)

        ids = [f"{user_id}_{idx}_{summary.source}" for idx, summary in enumerate(summaries)]
        documents = [
            "\n".join(
                [
                    summary.title,
                    summary.abstract,
                    summary.research_problem,
                    summary.innovation_summary,
                ]
            )
            for summary in summaries
        ]
        metadatas = [
            {
                "user_id": user_id,
                "source": summary.source,
                "score": summary.score,
            }
            for summary in summaries
        ]

        if ids:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
