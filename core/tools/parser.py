from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.models import PaperCandidate


class ParseTool:
    FALLBACK_MARKERS = (
        "using abstract-only fallback",
        "pdf text extraction returned empty",
        "pdf parsing failed unexpectedly",
        "parser backend is not supported",
        "marker parser is unavailable or failed",
        "docling parser is unavailable or failed",
        "downloaded pdf path does not exist",
        "no downloaded pdf was available",
    )

    def __init__(
        self,
        markdown_dir: str = "data/markdown",
        backend: str = "marker",
        max_pages: int = 8,
        device: str = "cuda",
    ) -> None:
        self.markdown_dir = Path(markdown_dir)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.backend = backend.strip().lower()
        self.max_pages = max(1, max_pages)
        self.device = device.strip().lower()

    def parse_to_markdown(self, user_id: str, paper: PaperCandidate) -> PaperCandidate:
        user_dir = self.markdown_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        stem = paper.paper_id or paper.title.replace(" ", "_")[:60]
        target = user_dir / f"{stem}.md"
        extracted_body = self._extract_body_from_pdf(paper)
        published_at = paper.published_at.isoformat() if paper.published_at else ""
        paper_link = self._resolve_paper_link(paper)
        body = (
            f"# {paper.title}\n\n"
            f"Source: {paper.source}\n\n"
            f"Score: {paper.score}\n\n"
            f"Published Date: {published_at}\n\n"
            f"Link: {paper_link}\n\n"
            f"## Abstract\n\n{paper.abstract}\n"
            f"\n## Parsed Content\n\n{extracted_body}\n"
        )
        # Clean surrogate characters that cannot be encoded to UTF-8
        body = body.encode("utf-8", errors="ignore").decode("utf-8")
        target.write_text(body, encoding="utf-8")
        paper.markdown_path = str(target)
        return paper

    def _resolve_paper_link(self, paper: PaperCandidate) -> str:
        if paper.pdf_url:
            return paper.pdf_url
        if paper.source == "semantic_scholar" and paper.paper_id:
            return f"https://www.semanticscholar.org/paper/{paper.paper_id}"
        if paper.source == "arxiv" and paper.paper_id:
            return f"https://arxiv.org/abs/{paper.paper_id}"
        return ""

    @classmethod
    def is_fallback_content(cls, text: str) -> bool:
        lowered = (text or "").lower()
        return any(marker in lowered for marker in cls.FALLBACK_MARKERS)

    def _extract_body_from_pdf(self, paper: PaperCandidate) -> str:
        if not paper.download_path:
            return "No downloaded PDF was available; using abstract-only fallback."

        path = Path(paper.download_path)
        if not path.exists():
            return "Downloaded PDF path does not exist; using abstract-only fallback."

        if self.backend == "marker":
            marker_content = self._extract_with_marker(path)
            if marker_content:
                return marker_content
            return "Marker parser is unavailable or failed; using abstract-only fallback."

        if self.backend == "docling":
            docling_content = self._extract_with_docling(path)
            if docling_content:
                return docling_content
            return "Docling parser is unavailable or failed; using abstract-only fallback."

        if self.backend != "pypdf":
            return "Parser backend is not supported in this build; using abstract-only fallback."

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages[: self.max_pages]:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text.strip())

            if not chunks:
                return "PDF text extraction returned empty content; using abstract-only fallback."

            merged = "\n\n".join(chunks)
            return merged[:12000]
        except Exception:
            return "PDF parsing failed unexpectedly; using abstract-only fallback."

    def _extract_with_marker(self, path: Path) -> str | None:
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict

            device = self.device if self.device == "cuda" else None
            artifact_dict = create_model_dict(device=device)
            config = {"output_format": "markdown"}
            converter = PdfConverter(artifact_dict=artifact_dict, config=config)
            rendered = converter(str(path))
            text = rendered.markdown if hasattr(rendered, "markdown") else str(rendered)
            return text[:12000] if text and text.strip() else None
        except Exception:
            return None

    def _extract_with_docling(self, path: Path) -> str | None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.document import ConversionResult
            from docling_core.types.doc import DoclingDocument
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import ConversionStatus

            # Create converter with default settings
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption()
                }
            )

            # Convert the PDF
            result = converter.convert(str(path))

            # Check conversion status
            if result.status != ConversionStatus.SUCCESS:
                return None

            # Export to markdown
            markdown_text = result.document.export_to_markdown()

            # Limit output size
            if markdown_text and markdown_text.strip():
                return markdown_text[:12000]
            return None

        except Exception:
            return None
