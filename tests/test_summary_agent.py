from pathlib import Path
from datetime import UTC, datetime

from core.agents.summary_agent import SummaryAgent
from core.config import GlobalConfig, UserConfig
from core.models import PaperCandidate


def test_summary_agent_fallback_reads_markdown(tmp_path: Path) -> None:
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text("# Title\n\nSome markdown content for parsing.", encoding="utf-8")

    user = UserConfig(
        user_id="u1",
        interests=["Market Microstructure"],
        search_query="order book",
    )
    paper = PaperCandidate(
        source="arxiv",
        title="Test Paper",
        abstract="Test abstract",
        published_at=datetime.now(UTC),
        markdown_path=str(markdown_file),
    )
    agent = SummaryAgent(global_config=GlobalConfig(use_llm_summary=False))

    summaries = agent.run(user=user, papers=[paper], limit=1)

    assert len(summaries) == 1
    assert "Some markdown content for parsing." in summaries[0].research_problem
    assert "Some markdown content for parsing." in summaries[0].innovation_summary


def test_summary_agent_section_aware_fallback(tmp_path: Path) -> None:
    markdown_file = tmp_path / "paper_sections.md"
    markdown_file.write_text(
        "# Introduction\nSignal intro text.\n"
        "## Methodology\nMethod details here.\n"
        "## Results\nStrong result signal.\n",
        encoding="utf-8",
    )

    user = UserConfig(
        user_id="u2",
        interests=["High Frequency Trading"],
        search_query="order book",
    )
    paper = PaperCandidate(
        source="arxiv",
        title="Section Paper",
        abstract="Abstract",
        published_at=datetime.now(UTC),
        markdown_path=str(markdown_file),
    )
    agent = SummaryAgent(global_config=GlobalConfig(use_llm_summary=False))

    summary = agent.run(user=user, papers=[paper], limit=1)[0]
    assert "Signal intro text." in summary.research_problem
    assert "Method details here." in summary.innovation_summary
