from __future__ import annotations

import re
from datetime import datetime, timezone

from core.agents.base import AgentBase
from core.config import UserConfig
from core.models import PaperCandidate


class RankingAgent(AgentBase):
    name = "ranking-agent"

    def __init__(
        self,
        threshold: float = 6.0,
        min_relevance_ratio: float = 0.2,
        recency_window_days: int = 60,
    ) -> None:
        self.threshold = threshold
        self.min_relevance_ratio = min_relevance_ratio
        self.recency_window_days = max(1, int(recency_window_days))

    def run(self, user: UserConfig, candidates: list[PaperCandidate]) -> list[PaperCandidate]:
        ranked: list[PaperCandidate] = []
        for candidate in candidates:
            candidate.score = self._score(user, candidate)
            ranked.append(candidate)
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def keep(self, ranked: list[PaperCandidate]) -> list[PaperCandidate]:
        kept: list[PaperCandidate] = []
        for item in ranked:
            if item.score < self.threshold:
                continue
            if item.relevance_score < self.min_relevance_ratio:
                continue
            published_at = item.published_at
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - published_at).days, 0)
            if age_days > self.recency_window_days:
                continue
            kept.append(item)
        return kept

    def _score(self, user: UserConfig, candidate: PaperCandidate) -> float:
        text = f"{candidate.title} {candidate.abstract}".lower()
        interest_tokens = [token.lower().strip() for token in user.interests if token.strip()]
        primary_interest_tokens = interest_tokens[:2]

        phrase_hits = 0
        for token in interest_tokens:
            if token in text:
                phrase_hits += 1

        keyword_set = self._extract_keywords(interest_tokens)
        primary_keyword_set = self._extract_keywords(primary_interest_tokens)
        text_words = set(re.findall(r"[a-zA-Z]{3,}", text))
        keyword_hits = len(keyword_set.intersection(text_words))
        primary_keyword_hits = len(primary_keyword_set.intersection(text_words))

        if interest_tokens:
            phrase_ratio = phrase_hits / len(interest_tokens)
            # Avoid over-diluting relevance when user interests are broad phrases.
            keyword_ratio = min(1.0, keyword_hits / 3.0)
            relevance = max(phrase_ratio, keyword_ratio)

            if primary_keyword_set:
                primary_ratio = primary_keyword_hits / len(primary_keyword_set)
                # Keep preference for the first two user interests, but avoid hard filtering.
                relevance = min(1.0, relevance * 0.85 + primary_ratio * 0.15)
        else:
            relevance = 0.5

        published_at = candidate.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - published_at).days, 0)
        recency = max(0.0, 1.0 - min(age_days / float(self.recency_window_days), 1.0))

        # In production, no-interest-hit items should not pass only due to recency.
        if interest_tokens and phrase_hits == 0 and keyword_hits == 0:
            recency *= 0.2

        # Very weak penalty when there is no keyword overlap at all.
        if interest_tokens and keyword_hits == 0:
            relevance *= 0.9
            recency *= 0.95

        candidate.relevance_score = round(relevance, 4)
        candidate.recency_score = round(recency, 4)
        score = user.ranking_weights.relevance * relevance + user.ranking_weights.recency * recency
        return round(score * 10, 2)

    @staticmethod
    def _extract_keywords(interests: list[str]) -> set[str]:
        stop = {
            "and",
            "the",
            "for",
            "with",
            "from",
            "into",
            "in",
            "on",
            "of",
            "to",
            "using",
        }
        keywords: set[str] = set()
        for item in interests:
            for token in re.findall(r"[a-zA-Z]{3,}", item.lower()):
                if token in stop:
                    continue
                keywords.add(token)
        return keywords
