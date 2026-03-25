from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser

from core.config import SourceConfig, UserConfig
from core.models import PaperCandidate
from core.tools.sources.base import SourceConnector
from core.tools.sources.http_utils import get_text_with_retry


class BioRxivMedRxivRssConnector(SourceConnector):
    source_name = "biorxiv_medrxiv_rss"

    def __init__(self, source_config: SourceConfig):
        super().__init__(source_config)

    def fetch_candidates(self, user: UserConfig, limit: int = 2) -> list[PaperCandidate]:
        try:
            combined: list[PaperCandidate] = []
            feeds = [
                "https://connect.biorxiv.org/biorxiv_xml.php?subject=all",
                "https://connect.medrxiv.org/medrxiv_xml.php?subject=all",
            ]
            for feed_url in feeds:
                xml_text = get_text_with_retry(
                    url=feed_url,
                    params={},
                    timeout_seconds=self.source_config.timeout_seconds,
                    retry=self.source_config.retry,
                    source_name=self.source_name,
                )
                parsed = feedparser.parse(xml_text)
                for entry in parsed.entries[:limit]:
                    published_at = datetime.now(UTC)
                    published_text = entry.get("published") or entry.get("updated")
                    if published_text:
                        parsed_dt = parsedate_to_datetime(published_text)
                        if parsed_dt.tzinfo is None:
                            parsed_dt = parsed_dt.replace(tzinfo=UTC)
                        published_at = parsed_dt.astimezone(UTC)

                    combined.append(
                        PaperCandidate(
                            source=self.source_name,
                            title=entry.get("title", "Untitled RSS paper"),
                            abstract=entry.get("summary", ""),
                            published_at=published_at,
                            paper_id=entry.get("id", ""),
                        )
                    )
            return combined[:limit]
        except Exception:
            return []
