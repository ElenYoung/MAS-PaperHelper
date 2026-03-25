from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.agents.base import AgentBase
from core.agents.rerank_agent import RerankAgent
from core.config import AppConfig, UserConfig
from core.models import PaperCandidate
from core.query_builder import build_source_query, resolve_search_query
from core.tools.sources.circuit_breaker import InMemoryCircuitBreaker
from core.tools.sources.registry import SourceRegistry


def _extract_arxiv_id(text: str) -> str | None:
    """Extract arXiv ID from text (URL or ID format)."""
    if not text:
        return None
    # Match arXiv ID patterns: 2301.12345, 2301.12345v1, arxiv:2301.12345, etc.
    patterns = [
        r'arxiv[.:]?(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'/(\d{4}\.\d{4,5}(?:v\d+)?)\.pdf',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1)
    return None


def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    # Lowercase, remove punctuation, normalize whitespace
    normalized = title.lower()
    # Remove common suffixes/prefixes
    normalized = re.sub(r'\s*[-–—]\s*arxiv.*$', '', normalized)
    normalized = re.sub(r'\[arxiv:[^\]]+\]', '', normalized)
    # Remove non-alphanumeric except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


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

        # Check if we should search per-interest for better coverage
        search_per_interest = len(user.interests) > 1 and query_mode != "manual"

        def _fetch_one(connector, interest_query: str | None = None):
            if not self.circuit_breaker.allow(connector.source_name):
                return None, connector.source_name, False

            if interest_query:
                # Per-interest search
                source_query = build_source_query(
                    user=user.model_copy(update={"search_query": interest_query}),
                    source_name=connector.source_name,
                    mode="manual",  # Force manual mode for per-interest
                    source_query_templates=app_config.global_config.source_query_templates,
                )
            else:
                # Unified search
                source_query = build_source_query(
                    user=user,
                    source_name=connector.source_name,
                    mode=query_mode,
                    source_query_templates=app_config.global_config.source_query_templates,
                )

            if not source_query:
                return None, connector.source_name, False

            runtime_user = user.model_copy(update={"search_query": source_query})
            try:
                # Reduce limit per source when searching per-interest to avoid overload
                effective_limit = max(1, limit_per_source // 2) if interest_query else limit_per_source
                fetched = connector.fetch_candidates(user=runtime_user, limit=effective_limit)
                self.circuit_breaker.record_success(connector.source_name)
                return fetched, connector.source_name, True
            except Exception:
                self.circuit_breaker.record_failure(connector.source_name)
                return None, connector.source_name, False

        if search_per_interest:
            # Search for each interest separately to ensure coverage
            for interest in user.interests:
                interest_query = interest.strip()
                if not interest_query:
                    continue
                with ThreadPoolExecutor(max_workers=len(connectors) or 1) as pool:
                    futures = {pool.submit(_fetch_one, c, interest_query): c for c in connectors}
                    for future in as_completed(futures):
                        fetched, source_name, ok = future.result()
                        if ok and fetched:
                            # Tag candidates with the interest that found them
                            for candidate in fetched:
                                if not hasattr(candidate, '_source_interests'):
                                    candidate._source_interests = []
                                candidate._source_interests.append(interest)
                            all_candidates.extend(fetched)
                            if source_name not in sources_used:
                                sources_used.append(source_name)
        else:
            # Original unified search
            with ThreadPoolExecutor(max_workers=len(connectors) or 1) as pool:
                futures = {pool.submit(_fetch_one, c): c for c in connectors}
                for future in as_completed(futures):
                    fetched, source_name, ok = future.result()
                    if ok and fetched:
                        all_candidates.extend(fetched)
                        sources_used.append(source_name)

        # Deduplicate by normalized key (arxiv ID > normalized title)
        seen_keys: set[str] = set()
        unique_candidates: list[PaperCandidate] = []
        merge_count: dict[str, int] = {}  # Track how many sources found each paper

        for c in all_candidates:
            # Try to extract arXiv ID from various fields
            arxiv_id = _extract_arxiv_id(c.paper_id)
            if not arxiv_id:
                arxiv_id = _extract_arxiv_id(c.pdf_url)
            if not arxiv_id:
                arxiv_id = _extract_arxiv_id(c.abstract)

            if arxiv_id:
                key = f"arxiv:{arxiv_id}"
            else:
                # Fall back to normalized title
                key = _normalize_title(c.title)
                if not key:
                    key = f"{c.title}:{c.source}"

            if key not in seen_keys:
                seen_keys.add(key)
                unique_candidates.append(c)
                merge_count[key] = 1
            else:
                # Same paper from different source, increment count
                merge_count[key] = merge_count.get(key, 1) + 1

        rerank_agent = RerankAgent(global_config=app_config.global_config)
        unique_candidates = rerank_agent.run(query=effective_query, papers=unique_candidates)

        return unique_candidates, sources_used, effective_query
