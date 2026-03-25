from __future__ import annotations

from core.agents.base import AgentBase
from core.config import GlobalConfig
from core.models import PaperCandidate


class RerankAgent(AgentBase):
    name = "rerank-agent"

    def __init__(self, global_config: GlobalConfig) -> None:
        self.global_config = global_config

    def run(self, query: str, papers: list[PaperCandidate]) -> list[PaperCandidate]:
        if not self.global_config.use_cross_encoder:
            return papers

        try:
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception:
            return papers

        if not papers:
            return papers

        model = CrossEncoder(self.global_config.cross_encoder_model)
        pairs = [(query, f"{p.title}\n{p.abstract}") for p in papers]
        scores = model.predict(pairs)

        scored = list(zip(papers, scores, strict=False))
        scored.sort(key=lambda item: float(item[1]), reverse=True)
        return [item[0] for item in scored]
