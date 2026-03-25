"""Intelligent search pipeline with LLM-enhanced query expansion and relevance checking."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import AppConfig, UserConfig
    from core.models import PaperCandidate
    from core.tools.sources.registry import SourceRegistry

from core.agents.query_expansion_agent import QueryExpansionAgent, QueryStrategy
from core.agents.relevance_check_agent import RelevanceCheckAgent, RelevanceAnalysis
from core.query_builder import build_source_query
from core.tools.sources.circuit_breaker import InMemoryCircuitBreaker


class IntelligentSearchPipeline:
    """
    LLM-enhanced search pipeline with semantic relevance verification.

    Features:
    1. Query expansion: LLM generates structured search strategies per interest
    2. Multi-source retrieval: Parallel search with expanded queries
    3. LLM relevance check: Batch verification of paper-interest relevance
    4. Smart re-ranking: Combined score from LLM relevance + recency + original score
    """

    def __init__(
        self,
        app_config: AppConfig,
        source_registry: SourceRegistry,
        llm_model: str | None = None,
        llm_api_base: str | None = None,
        user_config: UserConfig | None = None,
    ) -> None:
        self.app_config = app_config
        self.source_registry = source_registry
        self.circuit_breaker = InMemoryCircuitBreaker()
        self.user_config = user_config

        # Initialize agents if LLM search is enabled
        if app_config.global_config.llm_search_enabled:
            self.query_agent = QueryExpansionAgent(
                global_config=app_config.global_config,
                user_config=user_config,
                model=llm_model,
                api_base=llm_api_base,
            )
            self.relevance_agent = RelevanceCheckAgent(
                global_config=app_config.global_config,
                user_config=user_config,
                model=llm_model,
                api_base=llm_api_base,
            )
        else:
            self.query_agent = None
            self.relevance_agent = None

    def is_available(self) -> bool:
        """Check if LLM-enhanced search is available."""
        return (
            self.app_config.global_config.llm_search_enabled
            and self.query_agent is not None
            and self.relevance_agent is not None
        )

    def search(
        self,
        user: UserConfig,
        limit_per_source: int = 30,  # Higher limit for LLM filtering
        relevance_threshold: float | None = None,
        batch_size: int | None = None,
    ) -> tuple[list[PaperCandidate], list[str], str, list[RelevanceAnalysis]]:
        """
        Execute intelligent search with LLM enhancement.

        Args:
            user: User configuration
            limit_per_source: Number of candidates to fetch per source (higher for LLM filtering)
            relevance_threshold: Minimum relevance score to keep (default from config)
            batch_size: Batch size for LLM relevance checking (default from config)

        Returns:
            Tuple of (filtered_candidates, sources_used, effective_query, analyses)
        """
        if relevance_threshold is None:
            relevance_threshold = getattr(
                self.app_config.global_config, "llm_relevance_threshold", 0.6
            )
        if batch_size is None:
            batch_size = getattr(
                self.app_config.global_config, "llm_analysis_batch_size", 12
            )

        # Stage 1: Query Expansion
        query_strategies = self._expand_queries(user)

        # Stage 2: Multi-source Retrieval (with higher limits)
        all_candidates, sources_used = self._retrieve_candidates(
            user=user,
            query_strategies=query_strategies,
            limit_per_source=limit_per_source,
        )

        if not all_candidates:
            return [], sources_used, "", []

        # Build effective query description
        effective_query = self._build_effective_query(query_strategies)

        # Stage 3: LLM Relevance Verification
        analyses = self.relevance_agent.analyze_papers(
            papers=all_candidates,
            interests=user.interests,
            batch_size=batch_size,
            threshold=relevance_threshold,
        )

        # Stage 4: Filter and Re-rank
        filtered_candidates = self._filter_and_rerank(
            candidates=all_candidates,
            analyses=analyses,
            threshold=relevance_threshold,
        )

        return filtered_candidates, sources_used, effective_query, analyses

    def _expand_queries(self, user: UserConfig) -> list[QueryStrategy]:
        """Stage 1: Generate structured query strategies for each interest."""
        if not self.query_agent:
            return []

        max_keywords = getattr(
            self.app_config.global_config, "query_expansion_max_keywords", 5
        )

        return self.query_agent.expand(user, max_keywords=max_keywords)

    def _retrieve_candidates(
        self,
        user: UserConfig,
        query_strategies: list[QueryStrategy],
        limit_per_source: int,
    ) -> tuple[list[PaperCandidate], list[str]]:
        """Stage 2: Retrieve candidates from multiple sources using expanded queries."""
        connectors = self.source_registry.build_for_user(
            app_config=self.app_config, user=user
        )

        all_candidates: list[PaperCandidate] = []
        sources_used: list[str] = []
        seen_ids: set[str] = set()

        def _fetch_with_strategy(connector, strategy: QueryStrategy | None = None):
            """Fetch papers using a specific query strategy."""
            if not self.circuit_breaker.allow(connector.source_name):
                return [], connector.source_name

            # Get source-specific query
            if strategy and connector.source_name in strategy.source_specific_queries:
                query = strategy.source_specific_queries[connector.source_name]
            elif strategy:
                query = " OR ".join(f'"{kw}"' for kw in strategy.core_keywords[:3])
            else:
                # Fallback to basic query
                from core.query_builder import resolve_search_query
                query = resolve_search_query(user=user, mode="interests")

            if not query:
                return [], connector.source_name

            try:
                # Create temporary user with expanded query
                temp_user = user.model_copy(update={"search_query": query})
                results = connector.fetch_candidates(user=temp_user, limit=limit_per_source)

                # Tag candidates with matched interest
                if strategy:
                    for r in results:
                        if hasattr(r, "matched_interests"):
                            r.matched_interests.append(strategy.interest)

                return results, connector.source_name

            except Exception:
                self.circuit_breaker.record_failure(connector.source_name)
                return [], connector.source_name

        # Search per interest if we have query strategies
        if query_strategies:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for connector in connectors:
                    for strategy in query_strategies:
                        future = executor.submit(_fetch_with_strategy, connector, strategy)
                        futures.append((future, connector.source_name, strategy.interest))

                for future, source_name, interest in futures:
                    try:
                        results, _ = future.result(timeout=30)
                        if results:
                            sources_used.append(source_name)
                            for r in results:
                                # Deduplication
                                pid = r.paper_id or _normalize_title(r.title)
                                if pid not in seen_ids:
                                    seen_ids.add(pid)
                                    # Ensure matched_interest is set
                                    if not hasattr(r, "matched_interests") or not r.matched_interests:
                                        r.matched_interests = [interest]
                                    all_candidates.append(r)
                    except Exception:
                        pass
        else:
            # Fallback: simple search without expansion
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(_fetch_with_strategy, connector): connector.source_name
                    for connector in connectors
                }

                for future in as_completed(futures):
                    source_name = futures[future]
                    try:
                        results, _ = future.result(timeout=30)
                        if results:
                            sources_used.append(source_name)
                            for r in results:
                                pid = r.paper_id or _normalize_title(r.title)
                                if pid not in seen_ids:
                                    seen_ids.add(pid)
                                    all_candidates.append(r)
                    except Exception:
                        pass

        return all_candidates, list(set(sources_used))

    def _filter_and_rerank(
        self,
        candidates: list[PaperCandidate],
        analyses: list[RelevanceAnalysis],
        threshold: float,
    ) -> list[PaperCandidate]:
        """Stage 4: Filter by relevance threshold and re-rank."""
        # Create analysis lookup
        analysis_map = {a.paper_id: a for a in analyses}

        # Filter and score candidates
        scored_candidates: list[tuple[PaperCandidate, float]] = []

        for candidate in candidates:
            pid = candidate.paper_id or _normalize_title(candidate.title)
            analysis = analysis_map.get(pid)

            if not analysis:
                # No analysis available (LLM failed), keep with medium score
                scored_candidates.append((candidate, 0.5))
                continue

            # Strict mode: only keep high confidence matches
            strict_mode = getattr(
                self.app_config.global_config, "llm_strict_mode", False
            )
            if strict_mode and analysis.match_confidence != "high":
                continue

            # Filter by threshold
            if analysis.relevance_score < threshold:
                continue

            # Calculate composite score
            # LLM relevance (60%) + recency (20%) + original score (20%)
            llm_score = analysis.relevance_score

            # Recency score (newer is better)
            from datetime import UTC, datetime
            now = datetime.now(UTC)
            age_days = (now - candidate.published_at).days
            recency_score = max(0, 1 - (age_days / 365))  # Linear decay over 1 year

            # Original source score (if available)
            original_score = getattr(candidate, "score", 0.5)

            composite_score = (llm_score * 0.6) + (recency_score * 0.2) + (original_score * 0.2)

            # Attach analysis to candidate for downstream use
            candidate.llm_relevance_score = analysis.relevance_score
            candidate.llm_match_confidence = analysis.match_confidence
            candidate.llm_reasoning = analysis.reasoning

            scored_candidates.append((candidate, composite_score))

        # Sort by composite score (descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        return [c for c, _ in scored_candidates]

    def _build_effective_query(self, strategies: list[QueryStrategy]) -> str:
        """Build human-readable effective query description."""
        if not strategies:
            return ""

        parts = []
        for s in strategies:
            keywords = " OR ".join(s.core_keywords[:3])
            parts.append(f"[{s.interest}: {keywords}]")

        return "; ".join(parts)


def _normalize_title(title: str) -> str:
    """Normalize title for deduplication."""
    import re

    normalized = title.lower()
    normalized = re.sub(r"\s*[-–—]\s*arxiv.*$", "", normalized)
    normalized = re.sub(r"\[arxiv:[^\]]+\]", "", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
