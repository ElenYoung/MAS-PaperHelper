from __future__ import annotations

from datetime import UTC, datetime

from core.config import SourceConfig, UserConfig
from core.models import PaperCandidate
from core.tools.sources.base import SourceConnector
from core.tools.sources.http_utils import get_json_with_retry


class SemanticScholarConnector(SourceConnector):
    source_name = "semantic_scholar"

    def __init__(self, source_config: SourceConfig):
        super().__init__(source_config)

    def fetch_candidates(self, user: UserConfig, limit: int = 3) -> list[PaperCandidate]:
        try:
            payload = get_json_with_retry(
                url="https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": user.search_query,
                    "limit": str(limit),
                    "fields": "title,abstract,year,paperId,url,openAccessPdf",
                },
                timeout_seconds=self.source_config.timeout_seconds,
                retry=self.source_config.retry,
                source_name=self.source_name,
            )
            rows = payload.get("data", [])
            papers: list[PaperCandidate] = []
            for row in rows:
                year = row.get("year") or datetime.now(UTC).year
                published_at = datetime(int(year), 1, 1, tzinfo=UTC)
                papers.append(
                    PaperCandidate(
                        source=self.source_name,
                        title=row.get("title") or "Untitled Semantic Scholar paper",
                        abstract=row.get("abstract") or "",
                        published_at=published_at,
                        paper_id=row.get("paperId") or "",
                        pdf_url=(row.get("openAccessPdf") or {}).get("url") or row.get("url") or "",
                    )
                )
            return papers
        except Exception:
            return []
