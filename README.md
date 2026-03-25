# MAS-PaperHelper

MAS-PaperHelper is a configurable multi-agent literature assistant for research workflows.
It helps you:

- Discover recent papers from multiple sources.
- Rank papers by interest relevance and recency.
- Download/parse PDFs into local markdown.
- Generate structured fields like Research Problem and Innovation.
- Persist workflow history and optionally vectorize summaries.

The project provides both CLI and Web UI usage, with most behavior controlled by `config/config.yaml`.

## Architecture Overview

Core workflow (LangGraph):

1. Discovery: fetch candidates from enabled sources.
2. Ranking: compute relevance + recency and filter by thresholds.
3. Download & Parse: fetch PDF and convert into markdown.
4. Summary: generate structured summary fields.
5. KB Update: update keyword knowledge base and optional vector store.

Default node chain:

`Discovery -> Ranking -> Download&Parse -> Summary -> KB Update`

## Features

- Multi-user profile support in one config file.
- Source-level controls (enable, priority, rate limit, timeout, retry).
- Auto query generation from interests (`manual/interests/merge`).
- Recency window filtering (for example, last 60 days).
- Structured summary output with configurable language and max length.
- Expanded interests / keyword learning with whitelist and blacklist.
- Interest tags per paper + grouped display in UI.
- Web controls for major settings and one-click run.

## Environment Setup

Python requirement:

- Python `>=3.12`

Install dependencies with `uv`:

```bash
uv sync --extra dev
```

Optional extras:

```bash
uv sync --extra google --extra vector --extra database --extra rerank
```

- `google`: Google Scholar connector (`scholarly`)
- `vector`: Chroma vector store
- `database`: ClickHouse backend
- `rerank`: Cross-encoder reranking

## Project Structure

```text
.
├── config/
│   └── config.yaml
├── core/
│   ├── agents/
│   ├── tools/
│   ├── database/
│   ├── vector/
│   └── ...
├── scripts/
│   └── main.py
├── web/
│   ├── app.py
│   └── templates/
├── data/
│   ├── storage/
│   ├── markdown/
│   ├── keyword_kb.json
│   └── app.db
└── README.md
```

## Configuration Guide

All runtime behavior is controlled by `config/config.yaml`.

### 1) `global`

Model and runtime controls:

- `llm_provider`: `ollama` or `openai`
- `base_model`, `embedding_model`
- `base_model_api_base`, `embedding_api_base`
- `llm_api_key_env`
- `max_concurrent_tasks`

Ranking/retrieval controls:

- `ranking_threshold`: total score threshold
- `min_relevance_ratio`: relevance floor
- `recency_window_days`: only keep papers in this age window
- `discovery_limit_per_source`: fetch count per source

Summary controls:

- `use_llm_summary`: whether LLM summarization is enabled
- `summary_language`: `zh` or `en`
- `summary_max_chars`: max chars for each summary field
- `summary_limit`: number of summaries per run

Parsing controls:

- `parser_backend`: `pypdf` / `marker` / `docling`
- `parser_max_pages`

Query controls:

- `auto_query_from_interests`
- `auto_query_mode`: `manual` / `interests` / `merge`
- `source_query_templates`

Keyword KB controls:

- `keyword_kb_enabled`
- `keyword_kb_path`
- `keyword_expand_limit`
- `keyword_max_new_terms_per_run`
- `keyword_whitelist`
- `keyword_blacklist`

### 2) `database`

- `backend`: `sqlite` or `clickhouse`
- `sqlite_path`
- `clickhouse_dsn`

### 3) `vector_store`

- `backend`: `none` or vector backend
- `chroma_path`

### 4) `sources`

Each source has:

- `enabled`
- `priority`
- `rate_limit_per_min`
- `timeout_seconds`
- `retry`

Supported source keys:

- `arxiv`
- `semantic_scholar`
- `biorxiv_medrxiv_rss`
- `google_scholar`

### 5) `users`

Each user profile supports:

- `user_id`
- `interests`
- `search_query`
- `update_frequency`: `hourly` / `daily` / `weekly`
- `enabled_sources`
- `ranking_weights.recency`
- `ranking_weights.relevance`
- `llm_api_key` (optional per-user key)

## Usage Guide

### A) Run from CLI

Run one user once:

```bash
uv run python scripts/main.py run-once --user-id quant
```

Start scheduler loop:

```bash
uv run python scripts/main.py schedule --interval-seconds 300
```

Run diagnostics:

```bash
uv run python scripts/main.py doctor
```

### B) Run Web UI

Start server:

```bash
uv run uvicorn web.app:app --reload
```

Open:

- http://127.0.0.1:8000

Main pages:

- Config: run workflow, update source/user/global settings.
- Results: grouped papers, tags, and structured summary fields.
- Logs: recent run history.

Operational endpoints:

- `GET /healthz`
- `GET /api/diagnostics`

## Recommended Configuration Patterns

For quantitative finance tracking:

- Keep `recency_window_days: 60`.
- Keep `auto_query_mode: interests`.
- Tune `keyword_whitelist` with domain phrases.
- Increase `discovery_limit_per_source` if recall is low.
- Enable `use_llm_summary: true` when you need stable bilingual output quality.

For stricter relevance:

- Increase `min_relevance_ratio`.
- Increase `ranking_threshold`.

For broader recall:

- Lower `ranking_threshold` moderately.
- Increase `discovery_limit_per_source` and `summary_limit`.

## Data Outputs

- Downloaded PDFs: `data/storage/<user_id>/`
- Parsed markdown: `data/markdown/<user_id>/`
- Keyword KB: `data/keyword_kb.json`
- SQLite history: `data/app.db`
- Optional vector DB: `data/vector_db/`

## Troubleshooting

1. `No candidates passed threshold`

- Lower `ranking_threshold` or `min_relevance_ratio`.
- Increase `discovery_limit_per_source`.
- Verify query mode and interests.

2. Summary quality is noisy

- Set `use_llm_summary: true`.
- Adjust `summary_max_chars`.
- Switch parser backend if PDF extraction quality is poor.

3. Source has no results

- Check source `enabled` and user `enabled_sources`.
- Run `doctor` and inspect endpoint diagnostics.

4. Language does not change as expected

- Confirm `summary_language` in config and UI.
- For strongest effect, enable `use_llm_summary: true`.

## Development Notes

- Lint/test:

```bash
uv run pytest -q
```

- This repository focuses on configurable workflow correctness first; advanced citation-level summarization and richer document understanding can be added incrementally.
