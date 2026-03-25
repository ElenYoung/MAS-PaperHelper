from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree

from core.config import SourceConfig, UserConfig
from core.models import PaperCandidate
from core.tools.sources.base import SourceConnector
from core.tools.sources.http_utils import get_text_with_retry


class ArxivConnector(SourceConnector):
    source_name = "arxiv"

    def __init__(self, source_config: SourceConfig):
        super().__init__(source_config)

    def fetch_candidates(self, user: UserConfig, limit: int = 5) -> list[PaperCandidate]:
        try:
            xml_text = get_text_with_retry(
                url="https://export.arxiv.org/api/query",
                params={
                    "search_query": user.search_query,
                    "start": "0",
                    "max_results": str(limit),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                timeout_seconds=self.source_config.timeout_seconds,
                retry=self.source_config.retry,
                source_name=self.source_name,
            )
            return self._parse_arxiv_atom(xml_text)
        except Exception:
            return []

    def _parse_arxiv_atom(self, xml_text: str) -> list[PaperCandidate]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(xml_text)
        entries = root.findall("atom:entry", ns)
        papers: list[PaperCandidate] = []

        for entry in entries:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            published_text = entry.findtext("atom:published", default="", namespaces=ns)
            entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            published_at = datetime.now(UTC)
            if published_text:
                published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
            paper_id = entry_id.split("/")[-1] if entry_id else ""
            papers.append(
                PaperCandidate(
                    source=self.source_name,
                    title=title or "Untitled arXiv paper",
                    abstract=abstract,
                    published_at=published_at,
                    paper_id=paper_id,
                    pdf_url=f"https://arxiv.org/pdf/{paper_id}.pdf" if paper_id else "",
                )
            )
        return papers
