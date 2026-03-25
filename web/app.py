from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.config import get_user_config, load_config, save_config
from core.diagnostics import run_diagnostics
from core.database.factory import create_repository
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user

app = FastAPI(title="MAS-PaperHelper Skeleton")
templates = Jinja2Templates(directory="web/templates")


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
    search_query: str = Form(...),
    interests_csv: str = Form(...),
    update_frequency: str = Form(...),
    enabled_sources_csv: str = Form(...),
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
