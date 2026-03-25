from __future__ import annotations

from datetime import UTC, datetime

from core.config import SourceConfig, UserConfig
from core.models import PaperCandidate
from core.tools.sources.base import SourceConnector


class GoogleScholarConnector(SourceConnector):
    source_name = "google_scholar"

    def __init__(self, source_config: SourceConfig):
        super().__init__(source_config)

    def fetch_candidates(self, user: UserConfig, limit: int = 3) -> list[PaperCandidate]:
        try:
            from scholarly import scholarly  # type: ignore
        except Exception:
            return []

        results: list[PaperCandidate] = []
        try:
            search = scholarly.search_pubs(user.search_query)
            for _ in range(limit):
                item = next(search)
                bib = item.get("bib", {})
                year = bib.get("pub_year")
                published_at = datetime.now(UTC)
                if year and str(year).isdigit():
                    published_at = datetime(int(year), 1, 1, tzinfo=UTC)
                results.append(
                    PaperCandidate(
                        source=self.source_name,
                        title=bib.get("title") or "Untitled Google Scholar paper",
                        abstract=bib.get("abstract") or "",
                        published_at=published_at,
                        pdf_url=item.get("pub_url") or item.get("eprint_url") or "",
                    )
                )
        except StopIteration:
            return results
        except Exception:
            return results

        return results
