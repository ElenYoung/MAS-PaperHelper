from __future__ import annotations

import re

from core.config import UserConfig


def _normalize_terms(terms: list[str], limit: int = 8) -> list[str]:
    cleaned: list[str] = []
    for term in terms:
        value = term.strip()
        if not value:
            continue
        cleaned.append(value)
        if len(cleaned) >= limit:
            break
    return cleaned


def _build_interest_query(user: UserConfig) -> str:
    terms = _normalize_terms(user.interests)
    if not terms:
        return ""
    # Keep a source-neutral expression for cross-provider compatibility.
    return " OR ".join(f'"{term}"' for term in terms)


def _strip_arxiv_qualifiers(query: str) -> str:
    # Convert arXiv-specific operators into generic text for other providers.
    cleaned = re.sub(r"\b(?:abs|ti|au|cat|all):", "", query)
    cleaned = cleaned.replace("'", '"')
    cleaned = re.sub(r"\b(AND|OR|NOT)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[()]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _apply_template(source_name: str, query: str, templates: dict[str, str] | None) -> str:
    if not query:
        return ""

    default_templates: dict[str, str] = {
        "arxiv": "{query}",
        "semantic_scholar": "{query}",
        "google_scholar": "{query} research paper",
        "biorxiv_medrxiv_rss": "{query}",
    }
    merged = {**default_templates, **(templates or {})}
    template = merged.get(source_name, "{query}")
    try:
        rendered = template.format(query=query).strip()
    except Exception:
        rendered = query
    return re.sub(r"\s+", " ", rendered).strip()


def resolve_search_query(
    user: UserConfig,
    mode: str = "merge",
) -> str:
    manual_query = (user.search_query or "").strip()
    interest_query = _build_interest_query(user)

    if mode == "manual":
        return manual_query or interest_query

    if mode == "interests":
        return interest_query or manual_query

    # Default mode: merge manual and interest signals.
    if manual_query and interest_query:
        return f"({manual_query}) OR ({interest_query})"
    return manual_query or interest_query


def build_source_query(
    user: UserConfig,
    source_name: str,
    mode: str = "merge",
    source_query_templates: dict[str, str] | None = None,
) -> str:
    if source_name == "arxiv":
        raw_query = resolve_search_query(user=user, mode=mode)
        return _apply_template(source_name, raw_query, source_query_templates)

    manual_generic = _strip_arxiv_qualifiers((user.search_query or "").strip())
    generic_user = user.model_copy(update={"search_query": manual_generic})
    raw_query = resolve_search_query(user=generic_user, mode=mode)
    return _apply_template(source_name, raw_query, source_query_templates)
