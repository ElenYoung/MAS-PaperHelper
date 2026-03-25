from __future__ import annotations

import re
from pathlib import Path

from core.agents.base import AgentBase
from core.config import GlobalConfig, UserConfig
from core.llm.client import LLMClient
from core.models import PaperCandidate, PaperSummary
from core.tools.parser import ParseTool


class SummaryAgent(AgentBase):
    name = "summary-agent"

    def __init__(self, global_config: GlobalConfig) -> None:
        self.global_config = global_config

    def run(self, user: UserConfig, papers: list[PaperCandidate], limit: int = 3) -> list[PaperSummary]:
        summaries: list[PaperSummary] = []
        llm_client = LLMClient(global_config=self.global_config, user=user)
        for paper in papers[:limit]:
            markdown_text = self._read_markdown(paper.markdown_path)
            parsed_content = self._extract_parsed_content(markdown_text)
            if not parsed_content or ParseTool.is_fallback_content(parsed_content):
                continue
            section_view = self._extract_section_view(parsed_content)
            llm_summary = None
            if self.global_config.use_llm_summary:
                prompt = self._build_prompt(
                    user=user,
                    paper=paper,
                    parsed_content=parsed_content,
                    section_view=section_view,
                )
                llm_summary = llm_client.generate_summary(prompt)

            if llm_summary:
                summaries.append(
                    PaperSummary(
                        title=paper.title,
                        source=paper.source,
                        score=paper.score,
                        published_at=paper.published_at,
                        paper_url=self._resolve_paper_url(paper),
                        abstract=paper.abstract,
                        research_problem=self._finalize_field(
                            llm_summary["research_problem"],
                            kind="problem",
                            title=paper.title,
                        ),
                        innovation_summary=self._finalize_field(
                            llm_summary["innovation_summary"],
                            kind="innovation",
                            title=paper.title,
                        ),
                        matched_interests=self._match_interest_tags(
                            interests=user.interests,
                            title=paper.title,
                            abstract=paper.abstract,
                            parsed_content=parsed_content,
                        ),
                    )
                )
                continue

            summaries.append(
                PaperSummary(
                    title=paper.title,
                    source=paper.source,
                    score=paper.score,
                    published_at=paper.published_at,
                    paper_url=self._resolve_paper_url(paper),
                    abstract=paper.abstract,
                    research_problem=self._finalize_field(
                        self._fallback_research_problem(section_view=section_view, parsed_content=parsed_content),
                        kind="problem",
                        title=paper.title,
                    ),
                    innovation_summary=self._finalize_field(
                        self._fallback_innovation(section_view=section_view, parsed_content=parsed_content),
                        kind="innovation",
                        title=paper.title,
                    ),
                    matched_interests=self._match_interest_tags(
                        interests=user.interests,
                        title=paper.title,
                        abstract=paper.abstract,
                        parsed_content=parsed_content,
                    ),
                )
            )

            if summaries[-1].innovation_summary == summaries[-1].research_problem:
                alt = self._pick_alternative_sentence(
                    parsed_content=parsed_content,
                    current=summaries[-1].research_problem,
                )
                summaries[-1].innovation_summary = self._finalize_field(
                    alt,
                    kind="innovation",
                    title=paper.title,
                )
        return summaries

    def _match_interest_tags(
        self,
        interests: list[str],
        title: str,
        abstract: str,
        parsed_content: str,
    ) -> list[str]:
        text = f"{title} {abstract} {parsed_content[:4000]}".lower()
        tags: list[str] = []
        for interest in interests:
            term = interest.strip()
            if not term:
                continue
            lowered = term.lower()
            if lowered in text:
                tags.append(term)
                continue

            tokens = [t for t in re.findall(r"[a-zA-Z]{3,}", lowered) if t not in {"and", "for", "with", "the", "in", "of"}]
            if len(tokens) < 2:
                continue
            hit = sum(1 for tok in tokens if tok in text)
            if hit >= 2:
                tags.append(term)

        return tags

    def _resolve_paper_url(self, paper: PaperCandidate) -> str:
        if paper.pdf_url:
            return paper.pdf_url
        if paper.source == "semantic_scholar" and paper.paper_id:
            return f"https://www.semanticscholar.org/paper/{paper.paper_id}"
        if paper.source == "arxiv" and paper.paper_id:
            return f"https://arxiv.org/abs/{paper.paper_id}"
        return ""

    def _read_markdown(self, path: str) -> str:
        if not path:
            return ""
        file_path = Path(path)
        if not file_path.exists():
            return ""
        try:
            return file_path.read_text(encoding="utf-8")[:24000]
        except Exception:
            return ""

    def _build_prompt(
        self,
        user: UserConfig,
        paper: PaperCandidate,
        parsed_content: str,
        section_view: dict[str, str],
    ) -> str:
        language = "Chinese" if self.global_config.summary_language == "zh" else "English"
        max_chars = max(80, int(self.global_config.summary_max_chars))
        return (
            "You are a research assistant. Use only parsed full-text content from the paper body, "
            "not the abstract, to produce: (1) research_problem, (2) innovation_summary. "
            "Return strict JSON with keys research_problem, innovation_summary. "
            "Do not include title, author names, date, or section numbers. Keep each value concise, one paragraph, "
            f"max {max_chars} characters, language={language}.\n\n"
            f"User interests: {', '.join(user.interests)}\n"
            f"Title: {paper.title}\n"
            f"Section hints: {section_view}\n"
            f"Parsed content excerpt:\n{parsed_content}\n"
        )

    def _fallback_research_problem(
        self,
        section_view: dict[str, str],
        parsed_content: str,
    ) -> str:
        intro = section_view.get("introduction")
        if intro:
            return self._sentences_by_cues(
                intro,
                cues=["problem", "challenge", "question", "gap", "address", "aim", "goal", "task"],
                fallback_limit=2,
            )
        if parsed_content:
            return self._sentences_by_cues(
                parsed_content,
                cues=["problem", "challenge", "question", "gap", "address", "aim", "goal", "task"],
                fallback_limit=2,
            )
        return "Research problem could not be extracted from parsed full-text content."

    def _fallback_innovation(self, section_view: dict[str, str], parsed_content: str) -> str:
        method_text = section_view.get("methodology")
        if method_text:
            return self._sentences_by_cues(
                method_text,
                cues=["we propose", "novel", "new", "introduce", "contribution", "our method", "framework"],
                fallback_limit=2,
            )
        if parsed_content:
            return self._sentences_by_cues(
                parsed_content,
                cues=["we propose", "novel", "new", "introduce", "contribution", "our method", "framework"],
                fallback_limit=2,
            )
        return "Innovation details are unavailable due to missing parsed full-text content."

    def _extract_parsed_content(self, markdown_text: str) -> str:
        if not markdown_text:
            return ""
        marker = "## Parsed Content"
        idx = markdown_text.find(marker)
        if idx >= 0:
            return markdown_text[idx + len(marker) :].strip()
        return markdown_text.strip()

    def _sentences_by_cues(self, text: str, cues: list[str], fallback_limit: int = 2) -> str:
        normalized = self._clean_text(text)
        if not normalized:
            return ""

        sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", normalized) if chunk.strip()]
        filtered: list[str] = []
        for sentence in sentences:
            if len(sentence) < 35:
                continue
            digit_count = sum(ch.isdigit() for ch in sentence)
            if digit_count > max(6, len(sentence) // 5):
                continue
            filtered.append(sentence)

        sentences = filtered or sentences
        lowered_cues = [c.lower() for c in cues]
        selected = [
            sentence
            for sentence in sentences
            if any(cue in sentence.lower() for cue in lowered_cues)
        ]

        if not selected:
            selected = sentences[:fallback_limit]
        else:
            selected = selected[:fallback_limit]

        return " ".join(selected)

    def _clean_text(self, text: str) -> str:
        cleaned = text.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\b(?:abstract|introduction|conclusion|references|appendix)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+(?:\.\d+)*\b", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _finalize_field(self, text: str, kind: str, title: str = "") -> str:
        cleaned = self._clean_text(text)
        if title:
            cleaned = re.sub(re.escape(title), " ", cleaned, flags=re.IGNORECASE)

        # Remove common author/date fragments produced by noisy PDF extraction.
        cleaned = re.sub(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b\s+\d{1,2}(?:,\s*\d{4})?",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"^(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s*,?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^(research problem|innovation)\s*[:：-]?\s*", "", cleaned, flags=re.IGNORECASE)
        anchor = re.search(
            r"\b(we propose|we introduce|we develop|this paper|this study|addresses|to address|our method|our framework)\b",
            cleaned,
            flags=re.IGNORECASE,
        )
        if anchor and anchor.start() > 12:
            cleaned = cleaned[anchor.start() :]
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        max_chars = max(80, int(self.global_config.summary_max_chars))
        if len(cleaned) > max_chars:
            cleaned = cleaned[: max_chars - 3].rstrip() + "..."
        if cleaned:
            return cleaned

        if self.global_config.summary_language == "zh":
            if kind == "problem":
                return "未能从正文中可靠提取研究问题。"
            return "未能从正文中可靠提取创新点。"

        if kind == "problem":
            return "Could not reliably extract the research problem from full-text content."
        return "Could not reliably extract the innovation from full-text content."

    def _pick_alternative_sentence(self, parsed_content: str, current: str) -> str:
        cleaned = self._clean_text(parsed_content)
        sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", cleaned) if chunk.strip()]
        current_l = (current or "").lower()
        for sentence in sentences:
            if len(sentence) < 35:
                continue
            if sentence.lower() in current_l or current_l in sentence.lower():
                continue
            return sentence
        return current

    def _extract_section_view(self, markdown_text: str) -> dict[str, str]:
        if not markdown_text:
            return {}

        sections: dict[str, str] = {}
        lines = markdown_text.splitlines()
        current_header = ""
        buffer: list[str] = []

        def flush() -> None:
            nonlocal current_header, buffer
            if not current_header or not buffer:
                buffer = []
                return
            text = " ".join(part.strip() for part in buffer if part.strip())
            if text:
                lowered = current_header.lower()
                if re.search(r"intro|background", lowered):
                    sections.setdefault("introduction", text)
                if re.search(r"method|approach|model", lowered):
                    sections.setdefault("methodology", text)
                if re.search(r"result|experiment|evaluation", lowered):
                    sections.setdefault("results", text)
            buffer = []

        for line in lines:
            if line.startswith("#"):
                flush()
                current_header = line.lstrip("#").strip()
                continue
            buffer.append(line)

        flush()
        return sections
