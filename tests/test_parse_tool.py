from datetime import UTC, datetime

from core.models import PaperCandidate
from core.tools.parser import ParseTool


def test_parse_tool_writes_markdown_without_pdf(tmp_path) -> None:
    tool = ParseTool(markdown_dir=str(tmp_path), backend="pypdf", max_pages=2)
    paper = PaperCandidate(
        source="arxiv",
        title="Paper Title",
        abstract="Abstract content",
        published_at=datetime.now(UTC),
        paper_id="p1",
        download_path="",
    )

    out = tool.parse_to_markdown(user_id="u1", paper=paper)
    assert out.markdown_path
    content = (tmp_path / "u1" / "p1.md").read_text(encoding="utf-8")
    assert "## Parsed Content" in content
    assert "fallback" in content.lower()
