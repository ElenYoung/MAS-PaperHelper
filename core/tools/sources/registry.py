from __future__ import annotations

from typing import Callable

from core.config import AppConfig, SourceConfig, UserConfig
from core.tools.sources.arxiv import ArxivConnector
from core.tools.sources.base import SourceConnector
from core.tools.sources.biorxiv_rss import BioRxivMedRxivRssConnector
from core.tools.sources.google_scholar import GoogleScholarConnector
from core.tools.sources.semantic_scholar import SemanticScholarConnector

ConnectorFactory = Callable[[SourceConfig], SourceConnector]


class SourceRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ConnectorFactory] = {
            "arxiv": ArxivConnector,
            "semantic_scholar": SemanticScholarConnector,
            "biorxiv_medrxiv_rss": BioRxivMedRxivRssConnector,
            "google_scholar": GoogleScholarConnector,
        }

    def available_sources(self) -> list[str]:
        return sorted(self._factories.keys())

    def build_for_user(self, app_config: AppConfig, user: UserConfig) -> list[SourceConnector]:
        connectors: list[SourceConnector] = []
        selected = user.enabled_sources or list(app_config.sources.keys())

        for source_name in selected:
            source_cfg = app_config.sources.get(source_name)
            factory = self._factories.get(source_name)
            if not source_cfg or not source_cfg.enabled:
                continue
            if not factory:
                continue
            connectors.append(factory(source_cfg))

        connectors.sort(
            key=lambda connector: app_config.sources[connector.source_name].priority
        )
        return connectors
