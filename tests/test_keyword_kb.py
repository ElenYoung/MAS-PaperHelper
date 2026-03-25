from datetime import datetime, timezone

from core.keyword_kb import KeywordKnowledgeBase
from core.models import PaperCandidate


def test_keyword_kb_can_expand_and_learn(tmp_path) -> None:
    kb_file = tmp_path / "keyword_kb.json"
    kb = KeywordKnowledgeBase(path=str(kb_file))

    base = ["Market Microstructure", "High Frequency Trading"]
    expanded_before = kb.expand_interests("u1", base, limit=10)
    assert expanded_before == base

    papers = [
        PaperCandidate(
            source="arxiv",
            title="Reinforcement Learning for Portfolio Optimization",
            abstract="We study factor risk and portfolio allocation in quantitative trading.",
            published_at=datetime.now(timezone.utc),
        ),
        PaperCandidate(
            source="arxiv",
            title="Order Flow and Market Microstructure in Electronic Trading",
            abstract="Order flow dynamics for high frequency market making.",
            published_at=datetime.now(timezone.utc),
        ),
    ]

    kb.update_from_papers(user_id="u1", seed_interests=base, papers=papers, max_new_terms=20)

    expanded_after = kb.expand_interests("u1", base, limit=10)
    assert len(expanded_after) >= len(base)

    domains = kb.related_domains("u1")
    assert isinstance(domains, list)
    assert len(domains) >= 1


def test_keyword_kb_blacklist_blocks_expansion(tmp_path) -> None:
    kb_file = tmp_path / "keyword_kb.json"
    kb = KeywordKnowledgeBase(path=str(kb_file))

    papers = [
        PaperCandidate(
            source="arxiv",
            title="Factor Risk in Quantitative Trading",
            abstract="Factor risk and market microstructure for quantitative trading.",
            published_at=datetime.now(timezone.utc),
        )
    ]
    kb.update_from_papers(
        user_id="u2",
        seed_interests=["Market Microstructure"],
        papers=papers,
        max_new_terms=20,
        blacklist=["factor risk"],
    )

    expanded = kb.expand_interests("u2", ["Market Microstructure"], limit=20, blacklist=["factor risk"])
    joined = " | ".join(expanded).lower()
    assert "factor risk" not in joined


def test_keyword_kb_whitelist_forces_terms(tmp_path) -> None:
    kb_file = tmp_path / "keyword_kb.json"
    kb = KeywordKnowledgeBase(path=str(kb_file))

    expanded = kb.expand_interests(
        "u3",
        ["Market Microstructure"],
        limit=10,
        whitelist=["portfolio optimization"],
    )
    joined = " | ".join(expanded).lower()
    assert "portfolio optimization" in joined
