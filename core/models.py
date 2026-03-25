from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PaperCandidate:
    source: str
    title: str
    abstract: str
    published_at: datetime
    paper_id: str = ""
    pdf_url: str = ""
    download_path: str = ""
    markdown_path: str = ""
    score: float = 0.0
    relevance_score: float = 0.0
    recency_score: float = 0.0


@dataclass
class PaperSummary:
    title: str
    source: str
    score: float
    published_at: datetime
    paper_url: str
    abstract: str
    research_problem: str
    innovation_summary: str
    matched_interests: list[str]


@dataclass
class WorkflowResult:
    user_id: str
    total_candidates: int
    kept_candidates: int
    sources_used: list[str]
    threshold: float
    summaries: list[PaperSummary]
    effective_query: str = ""
    expanded_interests: list[str] | None = None
    related_domains: list[str] | None = None
    grouped_summaries: dict[str, list[PaperSummary]] | None = None
