from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.config import get_user_config, load_config, save_config
from core.database.factory import create_repository
from core.diagnostics import run_diagnostics
from core.keyword_kb import KeywordKnowledgeBase
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user

app = FastAPI(title="MAS-PaperHelper Skeleton")
templates = Jinja2Templates(directory="web/templates")

# Global scheduler state
_scheduler_task: asyncio.Task | None = None
_scheduler_last_run: dict[str, datetime] = {}
_scheduler_enabled: bool = False
_scheduler_interval: int = 300  # 5 minutes check interval


def _serialize_datetime(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


async def _scheduler_loop():
    """Background scheduler that runs workflow for users based on their frequency setting."""
    global _scheduler_last_run, _scheduler_enabled

    source_registry = SourceRegistry()

    while _scheduler_enabled:
        app_config = load_config()
        repository = create_repository(app_config)

        for user in app_config.users:
            if not _should_run_user(user.user_id, user.update_frequency):
                continue

            try:
                result = run_workflow_for_user(
                    app_config=app_config,
                    user=user,
                    source_registry=source_registry,
                )
                repository.save_workflow_run(result)
                _scheduler_last_run[user.user_id] = datetime.now(UTC)
                print(
                    f"[scheduler] user={result.user_id} total={result.total_candidates} "
                    f"kept={result.kept_candidates} summaries={len(result.summaries)}"
                )
            except Exception as e:
                print(f"[scheduler] Error running workflow for {user.user_id}: {e}")

        # Wait for next check interval
        for _ in range(_scheduler_interval):
            if not _scheduler_enabled:
                break
            await asyncio.sleep(1)


def _should_run_user(user_id: str, frequency: str) -> bool:
    """Check if a user should run based on their frequency setting."""
    last = _scheduler_last_run.get(user_id)
    if last is None:
        return True

    now = datetime.now(UTC)
    normalized = frequency.strip().lower()
    windows = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
    }
    window = windows.get(normalized, timedelta(days=1))
    return (now - last) >= window


@app.on_event("startup")
async def startup_event():
    """Auto-start scheduler on startup if configured."""
    global _scheduler_enabled, _scheduler_task
    # Check if auto-start is enabled via env var or config
    import os
    if os.getenv("MAS_SCHEDULER_AUTO_START", "false").lower() == "true":
        _scheduler_enabled = True
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        print("[startup] Scheduler auto-started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop scheduler on shutdown."""
    global _scheduler_enabled, _scheduler_task
    _scheduler_enabled = False
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        print("[shutdown] Scheduler stopped")


@app.get("/api/scheduler/status", response_class=JSONResponse)
def scheduler_status() -> JSONResponse:
    """Get scheduler status."""
    return JSONResponse(
        content={
            "enabled": _scheduler_enabled,
            "check_interval_seconds": _scheduler_interval,
            "last_runs": {
                user_id: dt.isoformat() for user_id, dt in _scheduler_last_run.items()
            },
        }
    )


@app.post("/api/scheduler/start", response_class=JSONResponse)
def scheduler_start() -> JSONResponse:
    """Start the background scheduler."""
    global _scheduler_enabled, _scheduler_task

    if _scheduler_enabled and _scheduler_task and not _scheduler_task.done():
        return JSONResponse(content={"status": "already_running"})

    _scheduler_enabled = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return JSONResponse(content={"status": "started"})


@app.post("/api/scheduler/stop", response_class=JSONResponse)
def scheduler_stop() -> JSONResponse:
    """Stop the background scheduler."""
    global _scheduler_enabled, _scheduler_task

    _scheduler_enabled = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    return JSONResponse(content={"status": "stopped"})


@app.post("/api/scheduler/run-now", response_class=JSONResponse)
def scheduler_run_now(user_id: str = Form(...)) -> JSONResponse:
    """Manually trigger a run for a specific user via scheduler."""
    app_config = load_config()
    repository = create_repository(app_config)
    user = get_user_config(app_config, user_id)

    result = run_workflow_for_user(
        app_config=app_config,
        user=user,
        source_registry=SourceRegistry(),
    )
    repository.save_workflow_run(result)
    _scheduler_last_run[user_id] = datetime.now(UTC)

    return JSONResponse(
        content=json.loads(
            json.dumps(dataclasses.asdict(result), default=_serialize_datetime)
        )
    )


def _render_index(
    request: Request,
    app_config,
    repository,
    result=None,
) -> HTMLResponse:
    history = repository.list_recent_runs(limit=10)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "users": [u.user_id for u in app_config.users],
            "users_data": app_config.users,
            "sources": app_config.sources,
            "global_config": app_config.global_config,
            "result": result,
            "history": history,
        },
    )


@app.get("/healthz", response_class=JSONResponse)
def healthz() -> JSONResponse:
    app_config = load_config()
    report = run_diagnostics(app_config)
    status = 200 if report.get("overall_ok") else 503
    return JSONResponse(status_code=status, content=report)


@app.get("/api/diagnostics", response_class=JSONResponse)
def api_diagnostics() -> JSONResponse:
    app_config = load_config()
    report = run_diagnostics(app_config)
    return JSONResponse(status_code=200, content=report)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)
    return _render_index(request=request, app_config=app_config, repository=repository)


@app.post("/run", response_class=HTMLResponse)
def run_user(request: Request, user_id: str = Form(...)) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)
    user = get_user_config(app_config, user_id)
    result = run_workflow_for_user(
        app_config=app_config,
        user=user,
        source_registry=SourceRegistry(),
    )
    repository.save_workflow_run(result)
    return _render_index(
        request=request,
        app_config=app_config,
        repository=repository,
        result=result,
    )


@app.post("/api/run", response_class=JSONResponse)
def api_run_user(request: Request, user_id: str = Form(...)) -> JSONResponse:
    app_config = load_config()
    repository = create_repository(app_config)
    user = get_user_config(app_config, user_id)
    result = run_workflow_for_user(
        app_config=app_config,
        user=user,
        source_registry=SourceRegistry(),
    )
    repository.save_workflow_run(result)
    return JSONResponse(content=json.loads(json.dumps(dataclasses.asdict(result), default=_serialize_datetime)))


@app.post("/sources/toggle", response_class=HTMLResponse)
def toggle_source(
    request: Request,
    source_name: str = Form(...),
    enabled: str = Form(...),
) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)
    if source_name in app_config.sources:
        app_config.sources[source_name].enabled = enabled == "true"
        save_config(app_config)

    return _render_index(request=request, app_config=app_config, repository=repository)


@app.post("/users/update", response_class=HTMLResponse)
def update_user(
    request: Request,
    user_id: str = Form(...),
    search_query: str = Form(""),
    interests_csv: str = Form(""),
    update_frequency: str = Form("daily"),
    enabled_sources_csv: str = Form(""),
) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)

    interests = [item.strip() for item in interests_csv.split(",") if item.strip()]
    enabled_sources = [item.strip() for item in enabled_sources_csv.split(",") if item.strip()]

    for user in app_config.users:
        if user.user_id == user_id:
            user.search_query = search_query.strip()
            user.interests = interests
            user.update_frequency = update_frequency.strip().lower() or "daily"
            user.enabled_sources = enabled_sources
            break

    save_config(app_config)
    return _render_index(request=request, app_config=app_config, repository=repository)


@app.post("/settings/query/update", response_class=HTMLResponse)
def update_query_settings(
    request: Request,
    auto_query_from_interests: str = Form("false"),
    auto_query_mode: str = Form("merge"),
) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)

    app_config.global_config.auto_query_from_interests = auto_query_from_interests == "true"
    if auto_query_mode in {"manual", "interests", "merge"}:
        app_config.global_config.auto_query_mode = auto_query_mode
    save_config(app_config)

    return _render_index(request=request, app_config=app_config, repository=repository)


@app.post("/settings/keywords/update", response_class=HTMLResponse)
def update_keyword_settings(
    request: Request,
    keyword_kb_enabled: str = Form("false"),
    keyword_expand_limit: str = Form("10"),
    keyword_max_new_terms_per_run: str = Form("20"),
    recency_window_days: str = Form("60"),
    summary_language: str = Form("en"),
    summary_max_chars: str = Form("1000"),
    keyword_whitelist_csv: str = Form(""),
    keyword_blacklist_csv: str = Form(""),
) -> HTMLResponse:
    app_config = load_config()
    repository = create_repository(app_config)

    whitelist = [item.strip() for item in keyword_whitelist_csv.split(",") if item.strip()]
    blacklist = [item.strip() for item in keyword_blacklist_csv.split(",") if item.strip()]

    app_config.global_config.keyword_kb_enabled = keyword_kb_enabled == "true"
    try:
        app_config.global_config.keyword_expand_limit = max(1, int(keyword_expand_limit))
    except ValueError:
        pass
    try:
        app_config.global_config.keyword_max_new_terms_per_run = max(1, int(keyword_max_new_terms_per_run))
    except ValueError:
        pass
    try:
        app_config.global_config.recency_window_days = max(1, int(recency_window_days))
    except ValueError:
        pass
    if summary_language in {"zh", "en"}:
        app_config.global_config.summary_language = summary_language
    try:
        app_config.global_config.summary_max_chars = max(80, int(summary_max_chars))
    except ValueError:
        pass

    app_config.global_config.keyword_whitelist = whitelist
    app_config.global_config.keyword_blacklist = blacklist
    save_config(app_config)

    return _render_index(request=request, app_config=app_config, repository=repository)


@app.get("/api/history", response_class=JSONResponse)
def api_history(
    q: str = Query(""),
    user_id: str = Query(""),
    limit: int = Query(50),
) -> JSONResponse:
    app_config = load_config()
    repository = create_repository(app_config)
    results = repository.search_paper_history(
        user_id=user_id or None, query=q, limit=min(limit, 200)
    )
    return JSONResponse(content=results)


@app.get("/api/expanded-interests", response_class=JSONResponse)
def api_get_expanded_interests(user_id: str = Query(...)) -> JSONResponse:
    """Get expanded interests for a user from keyword knowledge base."""
    app_config = load_config()
    kb_path = app_config.global_config.keyword_kb_path
    kb = KeywordKnowledgeBase(path=kb_path)
    data = kb._load()
    user_data = data.get("users", {}).get(user_id, {})
    terms = user_data.get("terms", {})
    domains = user_data.get("related_domains", {})
    return JSONResponse(content={
        "user_id": user_id,
        "terms": [{"term": k, "score": v} for k, v in sorted(terms.items(), key=lambda x: x[1], reverse=True)],
        "domains": [{"domain": k, "score": v} for k, v in sorted(domains.items(), key=lambda x: x[1], reverse=True)],
        "updated_at": user_data.get("updated_at", ""),
    })


@app.post("/api/expanded-interests/add", response_class=JSONResponse)
def api_add_expanded_interest(user_id: str = Form(...), term: str = Form(...), score: float = Form(1.0)) -> JSONResponse:
    """Add or update a term in expanded interests."""
    app_config = load_config()
    kb_path = app_config.global_config.keyword_kb_path
    kb = KeywordKnowledgeBase(path=kb_path)
    data = kb._load()
    users = data.setdefault("users", {})
    bucket = users.setdefault(user_id, {"terms": {}, "related_domains": {}, "updated_at": ""})
    terms = bucket.setdefault("terms", {})
    terms[term.strip()] = round(float(score), 4)
    bucket["updated_at"] = datetime.now(UTC).isoformat()
    kb._save(data)
    return JSONResponse(content={"status": "ok", "term": term.strip(), "score": score})


@app.post("/api/expanded-interests/remove", response_class=JSONResponse)
def api_remove_expanded_interest(user_id: str = Form(...), term: str = Form(...)) -> JSONResponse:
    """Remove a term from expanded interests."""
    app_config = load_config()
    kb_path = app_config.global_config.keyword_kb_path
    kb = KeywordKnowledgeBase(path=kb_path)
    data = kb._load()
    user_data = data.get("users", {}).get(user_id, {})
    terms = user_data.get("terms", {})
    if term in terms:
        del terms[term]
        user_data["updated_at"] = datetime.now(UTC).isoformat()
        kb._save(data)
        return JSONResponse(content={"status": "ok", "removed": term})
    return JSONResponse(content={"status": "not_found", "term": term}, status_code=404)


@app.post("/settings/global/update", response_class=JSONResponse)
def update_global_settings(
    max_concurrent_tasks: str = Form("5"),
    ranking_threshold: str = Form("5.0"),
    min_relevance_ratio: str = Form("0.05"),
    summary_limit: str = Form("50"),
    discovery_limit_per_source: str = Form("8"),
    use_llm_summary: str = Form("true"),
    parser_backend: str = Form("pypdf"),
    parser_max_pages: str = Form("15"),
    parser_device: str = Form("cpu"),
    use_cross_encoder: str = Form("false"),
    cross_encoder_model: str = Form("cross-encoder/ms-marco-MiniLM-L-6-v2"),
) -> JSONResponse:
    """Update global runtime settings."""
    app_config = load_config()

    try:
        app_config.global_config.max_concurrent_tasks = max(1, int(max_concurrent_tasks))
    except ValueError:
        pass
    try:
        app_config.global_config.ranking_threshold = float(ranking_threshold)
    except ValueError:
        pass
    try:
        app_config.global_config.min_relevance_ratio = max(0.0, min(1.0, float(min_relevance_ratio)))
    except ValueError:
        pass
    try:
        app_config.global_config.summary_limit = max(0, int(summary_limit))
    except ValueError:
        pass
    try:
        app_config.global_config.discovery_limit_per_source = max(1, int(discovery_limit_per_source))
    except ValueError:
        pass

    app_config.global_config.use_llm_summary = use_llm_summary == "true"

    if parser_backend in {"pypdf", "docling"}:
        app_config.global_config.parser_backend = parser_backend

    try:
        app_config.global_config.parser_max_pages = max(1, int(parser_max_pages))
    except ValueError:
        pass

    if parser_device in {"cuda", "cpu"}:
        app_config.global_config.parser_device = parser_device

    app_config.global_config.use_cross_encoder = use_cross_encoder == "true"
    app_config.global_config.cross_encoder_model = cross_encoder_model.strip()

    save_config(app_config)
    return JSONResponse(content={"status": "ok"})


@app.post("/settings/source/update", response_class=JSONResponse)
def update_source_settings(
    source_name: str = Form(...),
    priority: str = Form("1"),
    rate_limit_per_min: str = Form("30"),
    timeout_seconds: str = Form("20"),
    retry: str = Form("2"),
) -> JSONResponse:
    """Update source-specific settings."""
    app_config = load_config()

    if source_name not in app_config.sources:
        return JSONResponse(content={"status": "error", "message": "Source not found"}, status_code=404)

    source = app_config.sources[source_name]
    try:
        source.priority = max(1, int(priority))
    except ValueError:
        pass
    try:
        source.rate_limit_per_min = max(1, int(rate_limit_per_min))
    except ValueError:
        pass
    try:
        source.timeout_seconds = max(1, int(timeout_seconds))
    except ValueError:
        pass
    try:
        source.retry = max(0, int(retry))
    except ValueError:
        pass

    save_config(app_config)
    return JSONResponse(content={"status": "ok"})


@app.post("/settings/user/weights/update", response_class=JSONResponse)
def update_user_weights(
    user_id: str = Form(...),
    recency_weight: str = Form("0.2"),
    relevance_weight: str = Form("0.8"),
) -> JSONResponse:
    """Update user ranking weights."""
    app_config = load_config()

    for user in app_config.users:
        if user.user_id == user_id:
            try:
                user.ranking_weights["recency"] = max(0.0, min(1.0, float(recency_weight)))
            except ValueError:
                pass
            try:
                user.ranking_weights["relevance"] = max(0.0, min(1.0, float(relevance_weight)))
            except ValueError:
                pass
            break

    save_config(app_config)
    return JSONResponse(content={"status": "ok"})
