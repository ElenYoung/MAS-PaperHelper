from core.config import UserConfig
from core.query_builder import build_source_query, resolve_search_query


def _make_user(search_query: str, interests: list[str]) -> UserConfig:
    return UserConfig(
        user_id="u1",
        interests=interests,
        search_query=search_query,
        update_frequency="daily",
        enabled_sources=["arxiv"],
    )


def test_resolve_query_merge_mode_combines_manual_and_interests() -> None:
    user = _make_user(
        search_query="abs: 'order book' AND cat:cs.LG",
        interests=["Market Microstructure", "High Frequency Trading"],
    )

    query = resolve_search_query(user=user, mode="merge")

    assert "order book" in query
    assert "Market Microstructure" in query
    assert " OR " in query


def test_resolve_query_interests_mode_uses_interests_when_available() -> None:
    user = _make_user(search_query="legacy query", interests=["Reinforcement Learning in Finance"])

    query = resolve_search_query(user=user, mode="interests")

    assert "Reinforcement Learning in Finance" in query
    assert "legacy query" not in query


def test_resolve_query_is_empty_when_both_empty() -> None:
    user = _make_user(search_query="", interests=[])

    query = resolve_search_query(user=user, mode="merge")

    assert query == ""


def test_build_source_query_strips_arxiv_operators_for_non_arxiv() -> None:
    user = _make_user(search_query="abs: 'order book' AND cat:cs.LG", interests=["Market Microstructure"])

    query = build_source_query(user=user, source_name="semantic_scholar", mode="merge")

    assert "abs:" not in query
    assert "cat:" not in query
    assert "Market Microstructure" in query


def test_build_source_query_applies_template() -> None:
    user = _make_user(search_query="", interests=["Market Microstructure"])

    query = build_source_query(
        user=user,
        source_name="google_scholar",
        mode="interests",
        source_query_templates={"google_scholar": "topic: {query}"},
    )

    assert query.startswith("topic:")
