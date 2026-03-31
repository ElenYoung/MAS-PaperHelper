from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.agents.discovery_agent import DiscoveryAgent, _extract_arxiv_id
from core.agents.ranking_agent import RankingAgent
from core.agents.summary_agent import SummaryAgent
from core.config import AppConfig, UserConfig
from core.database.factory import create_repository
from core.intelligent_search import IntelligentSearchPipeline
from core.keyword_kb import KeywordKnowledgeBase
from core.models import PaperCandidate, PaperSummary, WorkflowResult
from core.tools.download import DownloadTool
from core.tools.parser import ParseTool
from core.tools.sources.registry import SourceRegistry
from core.vector.factory import create_vector_store


class WorkflowState(TypedDict):
    app_config: AppConfig
    user: UserConfig
    source_registry: SourceRegistry
    repository: Any
    limit_per_source: int
    ranking_threshold: float
    summary_limit: int
    candidates: list[PaperCandidate]
    ranked: list[PaperCandidate]
    kept: list[PaperCandidate]
    summaries: list[PaperSummary]
    sources_used: list[str]
    effective_query: str
    expanded_interests: list[str]
    related_domains: list[str]


def _normalize_phrase(value: str) -> str:
    import re
    lowered = value.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _merge_with_whitelist(
    base_interests: list[str],
    whitelist: list[str],
    blacklist: list[str],
    limit: int,
) -> list[str]:
    """Merge base interests with whitelist, prioritizing whitelist terms."""
    deny = {_normalize_phrase(x) for x in blacklist if _normalize_phrase(x)}
    allow = [x.strip() for x in whitelist if x.strip()]

    merged: list[str] = []
    seen: set[str] = set()

    # Priority 1: Whitelist terms (these are explicitly configured)
    for term in allow:
        key = _normalize_phrase(term)
        if not key or key in seen:
            continue
        if key in deny:
            continue
        merged.append(term)
        seen.add(key)
        if len(merged) >= limit:
            return merged

    # Priority 2: Base interests (user's explicit interests)
    for term in base_interests:
        key = _normalize_phrase(term)
        if not key or key in seen:
            continue
        if key in deny:
            continue
        merged.append(term.strip())
        seen.add(key)
        if len(merged) >= limit:
            return merged

    return merged


def compile_workflow_graph() -> Any:
    graph = StateGraph(WorkflowState)

    def discovery_node(state: WorkflowState) -> dict[str, Any]:
        runtime_user = state["user"]
        base_interests = list(state["user"].interests)
        whitelist = state["app_config"].global_config.keyword_whitelist or []
        blacklist = state["app_config"].global_config.keyword_blacklist or []
        expand_limit = state["app_config"].global_config.keyword_expand_limit
        related_domains: list[str] = []

        # Always merge whitelist into expanded interests, regardless of kb enabled
        expanded_interests = _merge_with_whitelist(
            base_interests=base_interests,
            whitelist=whitelist,
            blacklist=blacklist,
            limit=expand_limit,
        )

        if state["app_config"].global_config.keyword_kb_enabled:
            kb = KeywordKnowledgeBase(
                path=state["app_config"].global_config.keyword_kb_path,
                global_config=state["app_config"].global_config,
            )
            expanded_interests = kb.expand_interests(
                user_id=state["user"].user_id,
                base_interests=base_interests,
                limit=expand_limit,
                whitelist=whitelist,
                blacklist=blacklist,
            )
            related_domains = kb.related_domains(user_id=state["user"].user_id)

        runtime_user = state["user"].model_copy(update={"interests": expanded_interests})

        # Check if LLM-enhanced search is enabled
        if state["app_config"].global_config.llm_search_enabled:
            # Use Intelligent Search Pipeline
            pipeline = IntelligentSearchPipeline(
                app_config=state["app_config"],
                source_registry=state["source_registry"],
                llm_model=state["app_config"].global_config.llm_analysis_model or None,
                llm_api_base=state["app_config"].global_config.llm_api_base,
                user_config=state["user"],
            )

            if pipeline.is_available():
                # Use higher limit for LLM filtering
                discovery_limit = max(state["limit_per_source"], 30)

                candidates, sources_used, effective_query, analyses = pipeline.search(
                    user=runtime_user,
                    limit_per_source=discovery_limit,
                    relevance_threshold=state["app_config"].global_config.llm_relevance_threshold,
                    batch_size=state["app_config"].global_config.llm_analysis_batch_size,
                )

                # Attach LLM analysis metadata to candidates
                for candidate in candidates:
                    if hasattr(candidate, "llm_relevance_score"):
                        # Already attached in pipeline
                        pass
            else:
                # Fallback to simple search if pipeline not available
                agent = DiscoveryAgent(source_registry=state["source_registry"])
                candidates, sources_used, effective_query = agent.run(
                    app_config=state["app_config"],
                    user=runtime_user,
                    limit_per_source=state["limit_per_source"],
                )
        else:
            # Use original simple search (fallback)
            agent = DiscoveryAgent(source_registry=state["source_registry"])
            candidates, sources_used, effective_query = agent.run(
                app_config=state["app_config"],
                user=runtime_user,
                limit_per_source=state["limit_per_source"],
            )

        repo = state.get("repository")
        if repo:
            seen = repo.get_seen_paper_ids(state["user"].user_id)
            # Build normalized seen set for cross-source deduplication
            seen_normalized: set[str] = set()
            for pid in seen:
                seen_normalized.add(pid)
                # Also add standardized arXiv ID if extractable
                if arxiv_id := _extract_arxiv_id(pid):
                    seen_normalized.add(f"arxiv:{arxiv_id}")

            # Filter candidates using both original and normalized ID
            filtered_candidates: list[PaperCandidate] = []
            for c in candidates:
                # Check original ID
                if c.paper_id and c.paper_id in seen_normalized:
                    continue
                # Check normalized arXiv ID
                candidate_arxiv = _extract_arxiv_id(c.paper_id)
                if candidate_arxiv and f"arxiv:{candidate_arxiv}" in seen_normalized:
                    continue
                filtered_candidates.append(c)
            candidates = filtered_candidates

        return {
            "candidates": candidates,
            "sources_used": sources_used,
            "effective_query": effective_query,
            "expanded_interests": expanded_interests,
            "related_domains": related_domains,
        }

    def ranking_node(state: WorkflowState) -> dict[str, Any]:
        agent = RankingAgent(
            threshold=state["ranking_threshold"],
            min_relevance_ratio=state["app_config"].global_config.min_relevance_ratio,
            recency_window_days=state["app_config"].global_config.recency_window_days,
            ranking_weights=state["app_config"].global_config.ranking_weights,
        )
        ranked = agent.run(user=state["user"], candidates=state["candidates"])
        kept = agent.keep(ranked=ranked)
        return {"ranked": ranked, "kept": kept}

    def summary_node(state: WorkflowState) -> dict[str, Any]:
        agent = SummaryAgent(global_config=state["app_config"].global_config)
        summaries = agent.run(
            user=state["user"],
            papers=state["kept"],
            limit=state["summary_limit"],
        )
        return {"summaries": summaries}

    def download_parse_node(state: WorkflowState) -> dict[str, Any]:
        downloader = DownloadTool()
        parser = ParseTool(
            backend=state["app_config"].global_config.parser_backend,
            max_pages=state["app_config"].global_config.parser_max_pages,
            device=state["app_config"].global_config.parser_device,
        )
        user_id = state["user"].user_id

        def _process_one(paper: PaperCandidate) -> PaperCandidate:
            # Try to download and parse PDF, but keep paper even if it fails
            # SummaryAgent will fall back to abstract if needed
            if paper.pdf_url:
                downloaded = downloader.download_paper(user_id=user_id, paper=paper)
                parsed_paper = parser.parse_to_markdown(user_id=user_id, paper=downloaded)
                # Check if we got valid parsed content
                if parsed_paper.markdown_path:
                    try:
                        markdown_text = Path(parsed_paper.markdown_path).read_text(encoding="utf-8")
                        marker = "## Parsed Content"
                        parsed_content = markdown_text.split(marker, 1)[1].strip() if marker in markdown_text else ""
                        if parsed_content and not ParseTool.is_fallback_content(parsed_content):
                            return parsed_paper  # Successfully parsed
                    except Exception:
                        pass
            # Return paper as-is (will use abstract in summary)
            return paper

        max_workers = min(len(state["kept"]), state["app_config"].global_config.max_concurrent_tasks) or 1
        parsed: list[PaperCandidate] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for result in pool.map(_process_one, state["kept"]):
                parsed.append(result)
        return {"kept": parsed}

    def kb_update_node(state: WorkflowState) -> dict[str, Any]:
        related_domains = state.get("related_domains", [])
        if state["app_config"].global_config.keyword_kb_enabled:
            kb = KeywordKnowledgeBase(
                path=state["app_config"].global_config.keyword_kb_path,
                global_config=state["app_config"].global_config,
            )
            kb.update_from_papers(
                user_id=state["user"].user_id,
                seed_interests=state.get("expanded_interests") or state["user"].interests,
                papers=state["kept"],
                max_new_terms=state["app_config"].global_config.keyword_max_new_terms_per_run,
                whitelist=state["app_config"].global_config.keyword_whitelist,
                blacklist=state["app_config"].global_config.keyword_blacklist,
            )
            related_domains = kb.related_domains(user_id=state["user"].user_id)

        store = create_vector_store(state["app_config"])
        if store and state["summaries"]:
            try:
                store.upsert_summaries(user_id=state["user"].user_id, summaries=state["summaries"])
            except Exception:
                pass

        repo = state.get("repository")
        if repo:
            repo.mark_papers_seen(state["user"].user_id, state["kept"])
            if state["summaries"]:
                repo.save_paper_summaries(state["user"].user_id, state["summaries"])

        return {"related_domains": related_domains}

    graph.add_node("discovery", discovery_node)
    graph.add_node("ranking", ranking_node)
    graph.add_node("download_parse", download_parse_node)
    graph.add_node("summary", summary_node)
    graph.add_node("kb_update", kb_update_node)

    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "ranking")
    graph.add_edge("ranking", "download_parse")
    graph.add_edge("download_parse", "summary")
    graph.add_edge("summary", "kb_update")
    graph.add_edge("kb_update", END)

    return graph.compile()


def run_graph_workflow(
    app_config: AppConfig,
    user: UserConfig,
    source_registry: SourceRegistry,
    limit_per_source: int = 3,
    ranking_threshold: float = 6.0,
    summary_limit: int = 3,
) -> WorkflowResult:
    app = compile_workflow_graph()
    repository = create_repository(app_config)
    initial_state: WorkflowState = {
        "app_config": app_config,
        "user": user,
        "source_registry": source_registry,
        "repository": repository,
        "limit_per_source": limit_per_source,
        "ranking_threshold": ranking_threshold,
        "summary_limit": summary_limit,
        "candidates": [],
        "ranked": [],
        "kept": [],
        "summaries": [],
        "sources_used": [],
        "effective_query": "",
        "expanded_interests": [],
        "related_domains": [],
    }
    final_state = app.invoke(initial_state)
    expanded_interests = final_state.get("expanded_interests", [])
    base_interests = list(user.interests)
    grouped_summaries: dict[str, list[PaperSummary]] = {}
    assigned_titles: set[str] = set()

    # Assign each summary to its best-matching interest only
    for summary in final_state["summaries"]:
        if not summary.matched_interests:
            continue
        # Use the first (best) matched interest as its primary group
        primary = summary.matched_interests[0]
        grouped_summaries.setdefault(primary, []).append(summary)
        assigned_titles.add(summary.title)

    # For any unassigned, try to find closest interest match
    for summary in final_state["summaries"]:
        if summary.title in assigned_titles:
            continue
        best_match = None
        best_score = 0
        text = f"{summary.title} {summary.abstract}".lower()
        for interest in base_interests:
            interest_lower = interest.lower()
            if interest_lower in text:
                score = len(interest_lower.split())
            else:
                words = set(interest_lower.split())
                text_words = set(text.split())
                score = len(words & text_words)
            if score > best_score:
                best_score = score
                best_match = interest
        if best_match:
            grouped_summaries.setdefault(best_match, []).append(summary)
        else:
            grouped_summaries.setdefault("综合", []).append(summary)

    return WorkflowResult(
        user_id=user.user_id,
        total_candidates=len(final_state["candidates"]),
        kept_candidates=len(final_state["kept"]),
        sources_used=final_state["sources_used"],
        threshold=ranking_threshold,
        summaries=final_state["summaries"],
        effective_query=final_state["effective_query"],
        expanded_interests=expanded_interests,
        related_domains=final_state.get("related_domains", []),
        grouped_summaries=grouped_summaries,
    )
