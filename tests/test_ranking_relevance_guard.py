from datetime import datetime, timezone

from core.agents.ranking_agent import RankingAgent
from core.config import UserConfig
from core.models import PaperCandidate


def test_keep_filters_low_relevance_even_if_recent() -> None:
    user = UserConfig(
        user_id="u1",
        interests=["Market Microstructure", "High Frequency Trading"],
        search_query="",
        update_frequency="daily",
        enabled_sources=["arxiv"],
    )

    unrelated_recent = PaperCandidate(
        source="arxiv",
        title="Computer Vision Benchmark",
        abstract="Image segmentation and object detection",
        published_at=datetime.now(timezone.utc),
    )

    related_recent = PaperCandidate(
        source="arxiv",
        title="High Frequency Trading with RL",
        abstract="Market microstructure and order flow modeling",
        published_at=datetime.now(timezone.utc),
    )

    agent = RankingAgent(threshold=4.0, min_relevance_ratio=0.2)
    ranked = agent.run(user=user, candidates=[unrelated_recent, related_recent])
    kept = agent.keep(ranked)

    titles = [p.title for p in kept]
    assert "High Frequency Trading with RL" in titles
    assert "Computer Vision Benchmark" not in titles
