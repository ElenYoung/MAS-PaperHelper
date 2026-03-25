from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from core.config import AppConfig
from core.database.factory import create_repository
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user


def run_scheduler_loop(app_config: AppConfig, interval_seconds: int = 300) -> None:
    source_registry = SourceRegistry()
    repository = create_repository(app_config)
    last_run_at: dict[str, datetime] = {}

    while True:
        for user in app_config.users:
            if not _should_run(user_id=user.user_id, frequency=user.update_frequency, last_run_at=last_run_at):
                continue
            result = run_workflow_for_user(
                app_config=app_config,
                user=user,
                source_registry=source_registry,
            )
            repository.save_workflow_run(result)
            last_run_at[user.user_id] = datetime.now(UTC)
            print(
                f"[scheduler] user={result.user_id} total={result.total_candidates} "
                f"kept={result.kept_candidates} threshold={result.threshold} "
                f"summaries={len(result.summaries)} sources={','.join(result.sources_used)}"
            )
        time.sleep(interval_seconds)


def _should_run(user_id: str, frequency: str, last_run_at: dict[str, datetime]) -> bool:
    last = last_run_at.get(user_id)
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
