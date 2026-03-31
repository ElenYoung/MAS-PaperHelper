"""LLM-based intelligent keyword extraction agent for domain-aware keyword expansion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import GlobalConfig, UserConfig

from core.llm import get_llm


@dataclass
class KeywordExtraction:
    """Extracted keyword with metadata."""

    term: str
    relevance_score: float  # 0-1, relevance to user's domain
    category: str  # e.g., "methodology", "concept", "application", "domain"
    reasoning: str  # why this keyword is relevant
    related_to: list[str]  # related user interests


@dataclass
class KeywordExtractionResult:
    """Result of keyword extraction from papers."""

    keywords: list[KeywordExtraction]
    domain_summary: str  # brief summary of the domain these papers belong to
    coherence_score: float  # 0-1, how coherent these keywords are with user's interests


class IntelligentKeywordAgent:
    """Use LLM to intelligently extract domain-relevant keywords from papers."""

    def __init__(
        self,
        global_config: GlobalConfig | None = None,
        user_config: UserConfig | None = None,
        model: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._llm = get_llm(
            model=model,
            api_base=api_base,
            global_config=global_config,
            user_config=user_config,
        )

    def extract_keywords(
        self,
        user_interests: list[str],
        papers_content: list[tuple[str, str]],  # list of (title, abstract)
        max_keywords: int = 10,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
    ) -> KeywordExtractionResult:
        """
        Extract intelligent keywords from papers based on user's domain interests.

        Args:
            user_interests: User's current interests
            papers_content: List of (title, abstract) tuples
            max_keywords: Maximum number of keywords to extract
            whitelist: Must-include terms
            blacklist: Must-exclude terms

        Returns:
            Structured keyword extraction result
        """
        if not papers_content or not user_interests:
            return KeywordExtractionResult(
                keywords=[],
                domain_summary="No papers to analyze",
                coherence_score=0.0,
            )

        # Build papers text
        papers_text = ""
        for i, (title, abstract) in enumerate(papers_content[:15], 1):  # Limit to 15 papers
            papers_text += f"\n[{i}] Title: {title}\n"
            papers_text += f"    Abstract: {abstract[:400]}{'...' if len(abstract) > 400 else ''}\n"

        interests_text = "\n".join(f"- {interest}" for interest in user_interests)
        whitelist_text = ", ".join(whitelist) if whitelist else "None"
        blacklist_text = ", ".join(blacklist) if blacklist else "None"

        prompt = f"""You are an academic research expert specializing in identifying domain-specific terminology and concepts. Your task is to analyze research papers and extract meaningful keywords that are semantically related to the user's research interests.

## User's Research Interests
{interests_text}

## Papers to Analyze
{papers_text}

## Constraints
- Whitelist (must include if relevant): {whitelist_text}
- Blacklist (must exclude): {blacklist_text}
- Maximum keywords to extract: {max_keywords}

## Extraction Guidelines

1. **Semantic Relevance First**
   - Only extract keywords that are SEMANTICALLY related to user's interests
   - Do NOT extract generic academic terms (e.g., "method", "framework", "approach", "results")
   - Do NOT extract isolated technical terms without domain context

2. **Focus on Domain Concepts**
   - Extract specific methodologies, techniques, or concepts in the user's domain
   - Look for compound terms that show domain expertise (e.g., "deep reinforcement learning", "market microstructure")
   - Prefer multi-word phrases over single words when they carry more meaning

3. **Category Classification**
   For each keyword, classify into one of:
   - "core_concept": Fundamental concepts in the domain
   - "methodology": Specific methods, algorithms, or techniques
   - "application": Practical applications or use cases
   - "related_field": Adjacent fields that might be relevant

4. **Relationship Mapping**
   - For each keyword, identify which user interest(s) it relates to
   - If a keyword doesn't clearly relate to any user interest, exclude it

5. **Quality Filters**
   - Exclude terms that appear in the blacklist
   - Exclude overly generic terms: "paper", "study", "research", "analysis", "data", "model", "system"
   - Exclude single words unless they are highly domain-specific
   - Prefer phrases that combine domain terms (e.g., "quantitative trading" > "trading")

## Output Format
Return a JSON object with this structure:
{{
  "keywords": [
    {{
      "term": "the extracted keyword or phrase",
      "relevance_score": 0.85,
      "category": "methodology",
      "reasoning": "Brief explanation of why this term is relevant to user's interests",
      "related_to": ["user interest 1", "user interest 2"]
    }},
    ...
  ],
  "domain_summary": "A brief 1-2 sentence summary of what domain these papers represent",
  "coherence_score": 0.75
}}

The coherence_score should reflect how well the extracted keywords collectively represent the user's research domain (0-1 scale).

Important: Only output valid JSON, no other text."""

        try:
            response = self._llm.complete(prompt)
            content = response.content.strip()

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result_data = json.loads(content)

            keywords = []
            for item in result_data.get("keywords", []):
                kw = KeywordExtraction(
                    term=item["term"],
                    relevance_score=item.get("relevance_score", 0.5),
                    category=item.get("category", "concept"),
                    reasoning=item.get("reasoning", ""),
                    related_to=item.get("related_to", []),
                )
                keywords.append(kw)

            return KeywordExtractionResult(
                keywords=keywords,
                domain_summary=result_data.get("domain_summary", ""),
                coherence_score=result_data.get("coherence_score", 0.5),
            )

        except Exception as e:
            # Fallback: return empty result on error
            return KeywordExtractionResult(
                keywords=[],
                domain_summary=f"Extraction failed: {e}",
                coherence_score=0.0,
            )

    def filter_and_rank_keywords(
        self,
        extraction_result: KeywordExtractionResult,
        existing_terms: list[str],
        min_relevance: float = 0.5,
    ) -> list[tuple[str, float]]:
        """
        Filter and rank extracted keywords for final selection.

        Returns:
            List of (term, score) tuples
        """
        existing_normalized = {self._normalize(t) for t in existing_terms}

        filtered: list[tuple[str, float]] = []
        seen: set[str] = set()

        for kw in extraction_result.keywords:
            # Skip low relevance
            if kw.relevance_score < min_relevance:
                continue

            # Skip duplicates
            normalized = self._normalize(kw.term)
            if normalized in seen or normalized in existing_normalized:
                continue

            seen.add(normalized)

            # Score combines relevance and category weight
            category_weight = {
                "core_concept": 1.2,
                "methodology": 1.1,
                "application": 1.0,
                "related_field": 0.9,
            }.get(kw.category, 1.0)

            final_score = kw.relevance_score * category_weight
            filtered.append((kw.term, final_score))

        # Sort by score descending
        filtered.sort(key=lambda x: x[1], reverse=True)
        return filtered

    @staticmethod
    def _normalize(term: str) -> str:
        """Normalize term for deduplication."""
        return term.strip().lower().replace("-", " ")
