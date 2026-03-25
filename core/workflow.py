from __future__ import annotations

from core.config import AppConfig, UserConfig
from core.langgraph_workflow import run_graph_workflow
from core.models import WorkflowResult
from core.tools.sources.registry import SourceRegistry


def run_workflow_for_user(
    app_config: AppConfig,
    user: UserConfig,
    source_registry: SourceRegistry,
    limit_per_source: int | None = None,
    ranking_threshold: float | None = None,
    summary_limit: int | None = None,
) -> WorkflowResult:
    if limit_per_source is None:
        limit_per_source = app_config.global_config.discovery_limit_per_source
    if ranking_threshold is None:
        ranking_threshold = app_config.global_config.ranking_threshold
    if summary_limit is None:
        summary_limit = app_config.global_config.summary_limit

    return run_graph_workflow(
        app_config=app_config,
        user=user,
        source_registry=source_registry,
        limit_per_source=limit_per_source,
        ranking_threshold=ranking_threshold,
        summary_limit=summary_limit,
    )
