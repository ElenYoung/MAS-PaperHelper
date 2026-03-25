from datetime import datetime, timedelta, timezone

from core.agents.ranking_agent import RankingAgent
from core.config import load_config
from core.models import PaperCandidate
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user


def test_ranking_agent_scores_interest_hits_higher() -> None:
    app_config = load_config("config/config.yaml")
    user = app_config.users[0]
    agent = RankingAgent(threshold=6.0)

    strong = PaperCandidate(
        source="arxiv",
        title="Order Book Dynamics",
        abstract="Market Microstructure for High Frequency Trading",
        published_at=datetime.now(timezone.utc),
    )
    weak = PaperCandidate(
        source="arxiv",
        title="Unrelated Topic",
        abstract="A different domain",
        published_at=datetime.now(timezone.utc) - timedelta(days=31),
    )

    ranked = agent.run(user=user, candidates=[weak, strong])
    assert ranked[0].title == "Order Book Dynamics"
    assert ranked[0].score > ranked[1].score


def test_workflow_returns_agent_summaries() -> None:
    app_config = load_config("config/config.yaml")
    user = app_config.users[0]

    result = run_workflow_for_user(
        app_config=app_config,
        user=user,
        source_registry=SourceRegistry(),
    )

    assert result.total_candidates > 0
    assert result.kept_candidates >= 0
    assert result.threshold == app_config.global_config.ranking_threshold
    assert isinstance(result.summaries, list)
