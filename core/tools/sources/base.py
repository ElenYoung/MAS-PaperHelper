from __future__ import annotations

from abc import ABC, abstractmethod

from core.config import SourceConfig, UserConfig
from core.models import PaperCandidate


class SourceConnector(ABC):
    source_name: str

    def __init__(self, source_config: SourceConfig):
        self.source_config = source_config

    @abstractmethod
    def fetch_candidates(self, user: UserConfig, limit: int = 5) -> list[PaperCandidate]:
        raise NotImplementedError
