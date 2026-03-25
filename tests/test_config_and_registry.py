from core.config import load_config
from core.tools.sources.registry import SourceRegistry


def test_registry_builds_enabled_sources_for_user() -> None:
    app_config = load_config("config/config.yaml")
    user = app_config.users[0]

    registry = SourceRegistry()
    connectors = registry.build_for_user(app_config=app_config, user=user)

    names = [c.source_name for c in connectors]
    assert "arxiv" in names
    assert "semantic_scholar" in names
    assert "biorxiv_medrxiv_rss" in names
    assert "google_scholar" not in names
