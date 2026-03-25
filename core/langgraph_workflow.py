from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.agents.discovery_agent import DiscoveryAgent
from core.agents.ranking_agent import RankingAgent
from core.agents.summary_agent import SummaryAgent
from core.config import AppConfig, UserConfig
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


def compile_workflow_graph() -> Any:
    graph = StateGraph(WorkflowState)

    def discovery_node(state: WorkflowState) -> dict[str, Any]:
        runtime_user = state["user"]
        expanded_interests = list(state["user"].interests)
        related_domains: list[str] = []

        if state["app_config"].global_config.keyword_kb_enabled:
            kb = KeywordKnowledgeBase(path=state["app_config"].global_config.keyword_kb_path)
            expanded_interests = kb.expand_interests(
                user_id=state["user"].user_id,
                base_interests=state["user"].interests,
                limit=state["app_config"].global_config.keyword_expand_limit,
                whitelist=state["app_config"].global_config.keyword_whitelist,
                blacklist=state["app_config"].global_config.keyword_blacklist,
            )
            related_domains = kb.related_domains(user_id=state["user"].user_id)
            runtime_user = state["user"].model_copy(update={"interests": expanded_interests})

        agent = DiscoveryAgent(source_registry=state["source_registry"])
        candidates, sources_used, effective_query = agent.run(
            app_config=state["app_config"],
            user=runtime_user,
            limit_per_source=state["limit_per_source"],
        )
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
        )
        parsed: list[PaperCandidate] = []
        for paper in state["kept"]:
            downloaded = downloader.download_paper(user_id=state["user"].user_id, paper=paper)
            parsed_paper = parser.parse_to_markdown(user_id=state["user"].user_id, paper=downloaded)
            if not parsed_paper.markdown_path:
                continue
            try:
                markdown_text = Path(parsed_paper.markdown_path).read_text(encoding="utf-8")
                marker = "## Parsed Content"
                parsed_content = markdown_text.split(marker, 1)[1].strip() if marker in markdown_text else ""
            except Exception:
                parsed_content = ""

            if not parsed_content or ParseTool.is_fallback_content(parsed_content):
                continue

            parsed.append(parsed_paper)
        return {"kept": parsed}

    def kb_update_node(state: WorkflowState) -> dict[str, Any]:
        related_domains = state.get("related_domains", [])
        if state["app_config"].global_config.keyword_kb_enabled:
            kb = KeywordKnowledgeBase(path=state["app_config"].global_config.keyword_kb_path)
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
    initial_state: WorkflowState = {
        "app_config": app_config,
        "user": user,
        "source_registry": source_registry,
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
    matched_titles: set[str] = set()

    for interest in base_interests:
        bucket = [s for s in final_state["summaries"] if interest in s.matched_interests]
        if bucket:
            grouped_summaries[interest] = bucket
            matched_titles.update(item.title for item in bucket)

    others = [s for s in final_state["summaries"] if s.title not in matched_titles]
    if others:
        grouped_summaries["Other"] = others

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
