from datetime import UTC, datetime

from core.agents.rerank_agent import RerankAgent
from core.config import GlobalConfig
from core.models import PaperCandidate
from core.tools.sources.circuit_breaker import InMemoryCircuitBreaker


def test_circuit_breaker_opens_after_failures() -> None:
    breaker = InMemoryCircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    name = "x"
    assert breaker.allow(name) is True
    breaker.record_failure(name)
    assert breaker.allow(name) is True
    breaker.record_failure(name)
    assert breaker.allow(name) is False


def test_rerank_agent_fallback_without_dependency() -> None:
    agent = RerankAgent(GlobalConfig(use_cross_encoder=True))
    papers = [
        PaperCandidate(
            source="arxiv",
            title="A",
            abstract="B",
            published_at=datetime.now(UTC),
        )
    ]
    out = agent.run("query", papers)
    assert out == papers
