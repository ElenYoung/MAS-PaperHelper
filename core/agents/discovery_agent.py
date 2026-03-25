from __future__ import annotations

from core.agents.base import AgentBase
from core.agents.rerank_agent import RerankAgent
from core.config import AppConfig, UserConfig
from core.models import PaperCandidate
from core.query_builder import build_source_query, resolve_search_query
from core.tools.sources.circuit_breaker import InMemoryCircuitBreaker
from core.tools.sources.registry import SourceRegistry


class DiscoveryAgent(AgentBase):
    name = "discovery-agent"

    def __init__(self, source_registry: SourceRegistry) -> None:
        self.source_registry = source_registry
        self.circuit_breaker = InMemoryCircuitBreaker()

    def run(
        self,
        app_config: AppConfig,
        user: UserConfig,
        limit_per_source: int = 3,
    ) -> tuple[list[PaperCandidate], list[str], str]:
        query_mode = "manual"
        if app_config.global_config.auto_query_from_interests:
            query_mode = app_config.global_config.auto_query_mode

        effective_query = resolve_search_query(user=user, mode=query_mode)
        if not effective_query:
            return [], [], ""

        connectors = self.source_registry.build_for_user(app_config=app_config, user=user)
        all_candidates: list[PaperCandidate] = []
        sources_used: list[str] = []

        for connector in connectors:
            if not self.circuit_breaker.allow(connector.source_name):
                continue

            source_query = build_source_query(
                user=user,
                source_name=connector.source_name,
                mode=query_mode,
                source_query_templates=app_config.global_config.source_query_templates,
            )
            if not source_query:
                continue

            runtime_user = user.model_copy(update={"search_query": source_query})

            try:
                fetched = connector.fetch_candidates(user=runtime_user, limit=limit_per_source)
                all_candidates.extend(fetched)
                sources_used.append(connector.source_name)
                self.circuit_breaker.record_success(connector.source_name)
            except Exception:
                self.circuit_breaker.record_failure(connector.source_name)

        rerank_agent = RerankAgent(global_config=app_config.global_config)
        all_candidates = rerank_agent.run(query=effective_query, papers=all_candidates)

        return all_candidates, sources_used, effective_query
