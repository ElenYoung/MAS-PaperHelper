from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.models import PaperCandidate


class KeywordKnowledgeBase:
    def __init__(self, path: str = "data/keyword_kb.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def expand_interests(
        self,
        user_id: str,
        base_interests: list[str],
        limit: int = 10,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
    ) -> list[str]:
        data = self._load()
        bucket = data.get("users", {}).get(user_id, {})
        learned = bucket.get("terms", {})
        deny = {self._normalize_phrase(x) for x in (blacklist or []) if self._normalize_phrase(x)}
        allow = [x.strip() for x in (whitelist or []) if x.strip()]

        if learned and deny:
            cleaned = {
                term: score
                for term, score in learned.items()
                if not self._is_denied_term(term, deny)
            }
            if len(cleaned) != len(learned):
                data.setdefault("users", {}).setdefault(user_id, {})["terms"] = cleaned
                self._save(data)
                learned = cleaned

        ordered = sorted(learned.items(), key=lambda item: float(item[1]), reverse=True)
        merged: list[str] = []
        seen: set[str] = set()

        # Priority 1: Whitelist terms (these are explicitly configured by user)
        for term in allow:
            key = self._normalize_phrase(term)
            if not key or key in seen:
                continue
            if key in deny:
                continue
            merged.append(term)
            seen.add(key)
            if len(merged) >= limit:
                return merged

        # Priority 2: Base interests (user's explicit interests)
        for term in base_interests:
            key = self._normalize_phrase(term)
            if not key or key in seen:
                continue
            if key in deny:
                continue
            merged.append(term.strip())
            seen.add(key)
            if len(merged) >= limit:
                return merged

        # Priority 3: Learned terms from knowledge base
        for term, _score in ordered:
            key = self._normalize_phrase(term)
            if not key or key in seen:
                continue
            if key in deny:
                continue
            merged.append(term)
            seen.add(key)
            if len(merged) >= limit:
                break

        return merged

    def update_from_papers(
        self,
        user_id: str,
        seed_interests: list[str],
        papers: list[PaperCandidate],
        max_new_terms: int = 20,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
    ) -> None:
        if not papers:
            return

        data = self._load()
        users = data.setdefault("users", {})
        bucket = users.setdefault(user_id, {"terms": {}, "related_domains": {}, "updated_at": ""})
        terms: dict[str, float] = bucket.setdefault("terms", {})
        domains: dict[str, float] = bucket.setdefault("related_domains", {})

        text_blob = "\n".join(f"{p.title}. {p.abstract}" for p in papers)
        extracted = self._extract_terms(text_blob)
        if not extracted:
            return

        deny = {self._normalize_phrase(x) for x in (blacklist or []) if self._normalize_phrase(x)}
        allow_raw = [x.strip() for x in (whitelist or []) if x.strip()]
        allow = {self._normalize_phrase(x) for x in allow_raw if self._normalize_phrase(x)}

        if terms and deny:
            bucket["terms"] = {
                term: score
                for term, score in terms.items()
                if not self._is_denied_term(term, deny)
            }
            terms = bucket["terms"]

        seed_set = {
            self._normalize_phrase(item)
            for item in seed_interests
            if self._normalize_phrase(item)
        }

        count = 0
        for term, weight in extracted:
            key = self._normalize_phrase(term)
            if not key:
                continue
            if key in seed_set:
                continue
            if self._is_denied_term(key, deny):
                continue
            if allow and key not in allow and not any(a in key or key in a for a in allow):
                continue
            terms[term] = round(float(terms.get(term, 0.0)) + float(weight), 4)
            count += 1
            if count >= max_new_terms:
                break

        for raw in allow_raw:
            key = self._normalize_phrase(raw)
            if not key or key in deny:
                continue
            terms[raw] = max(float(terms.get(raw, 0.0)), 1.0)

        inferred = self._infer_domains(list(terms.keys()) + seed_interests)
        for domain, score in inferred.items():
            domains[domain] = round(float(domains.get(domain, 0.0)) + float(score), 4)

        bucket["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)

    def related_domains(self, user_id: str, limit: int = 8) -> list[str]:
        data = self._load()
        bucket = data.get("users", {}).get(user_id, {})
        items = bucket.get("related_domains", {})
        ordered = sorted(items.items(), key=lambda item: float(item[1]), reverse=True)
        return [name for name, _ in ordered[:limit]]

    def _extract_terms(self, text: str) -> list[tuple[str, float]]:
        words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.lower())
        if not words:
            return []

        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
            "using",
            "based",
            "paper",
            "study",
            "method",
            "results",
            "their",
            "there",
            "these",
            "those",
            "both",
            "while",
            "does",
            "not",
            "into",
            "into",
            "over",
            "under",
            "between",
            "also",
            "such",
            "show",
            "shows",
            "framework",
            "approach",
            "problem",
            "propose",
            "proposed",
            "into",
        }
        filtered = [w for w in words if w not in stopwords]

        unigram_counts: dict[str, int] = {}
        for token in filtered:
            unigram_counts[token] = unigram_counts.get(token, 0) + 1

        bigram_counts: dict[str, int] = {}
        for i in range(len(filtered) - 1):
            a, b = filtered[i], filtered[i + 1]
            if a == b:
                continue
            if a in stopwords or b in stopwords:
                continue
            phrase = f"{a} {b}"
            bigram_counts[phrase] = bigram_counts.get(phrase, 0) + 1

        scored: dict[str, float] = {}
        for token, count in unigram_counts.items():
            if count < 2:
                continue
            if token in stopwords:
                continue
            scored[token] = float(count) * 0.5
        for phrase, count in bigram_counts.items():
            if count < 2:
                continue
            if any(part in stopwords for part in phrase.split()):
                continue
            scored[phrase] = float(count)

        ordered = sorted(scored.items(), key=lambda item: item[1], reverse=True)
        return ordered

    def _infer_domains(self, terms: list[str]) -> dict[str, float]:
        joined = " ".join(terms).lower()
        rules: dict[str, tuple[str, ...]] = {
            "Quantitative Finance": (
                "market",
                "microstructure",
                "order",
                "trading",
                "portfolio",
                "risk",
                "factor",
                "asset",
            ),
            "Machine Learning": (
                "learning",
                "reinforcement",
                "neural",
                "transformer",
                "agent",
                "optimization",
            ),
            "Time Series Forecasting": (
                "time series",
                "forecast",
                "temporal",
                "sequence",
                "volatility",
            ),
        }

        scores: dict[str, float] = {}
        for domain, keywords in rules.items():
            hit = 0
            for keyword in keywords:
                if keyword in joined:
                    hit += 1
            if hit > 0:
                scores[domain] = float(hit)
        return scores

    @staticmethod
    def _normalize_phrase(value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

    def _is_denied_term(self, value: str, deny_set: set[str]) -> bool:
        key = self._normalize_phrase(value)
        if not key:
            return False
        if key in deny_set:
            return True
        parts = set(key.split())
        return any(deny in parts for deny in deny_set)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"users": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"users": {}}

    def _save(self, payload: dict) -> None:
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
