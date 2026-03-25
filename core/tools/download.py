from __future__ import annotations

import re
from pathlib import Path

import httpx

from core.models import PaperCandidate


class DownloadTool:
    def __init__(self, base_dir: str = "data/storage") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def download_paper(self, user_id: str, paper: PaperCandidate) -> PaperCandidate:
        url = self._normalize_pdf_url(paper.pdf_url)
        if not url:
            return paper

        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", paper.title)[:80] or "paper"
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        target = user_dir / f"{safe_name}.pdf"

        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "MAS-PaperHelper/1.0 (+https://github.com/)"
                    },
                )
                response.raise_for_status()

            content_type = (response.headers.get("content-type") or "").lower()
            is_pdf = "application/pdf" in content_type or response.content.startswith(b"%PDF-")
            if not is_pdf:
                paper.download_path = ""
                return paper

            target.write_bytes(response.content)
            paper.download_path = str(target)
        except Exception:
            paper.download_path = ""

        return paper

    @staticmethod
    def _normalize_pdf_url(url: str) -> str:
        value = (url or "").strip()
        if not value:
            return ""

        if "arxiv.org/abs/" in value:
            arxiv_id = value.rsplit("/abs/", 1)[-1].strip("/")
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        return value
