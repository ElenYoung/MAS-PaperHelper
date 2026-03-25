from pathlib import Path

from core.config import load_config
from core.database.sqlite_repository import SqliteRepository
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user


def test_workflow_and_repository_persist(tmp_path: Path) -> None:
    app_config = load_config("config/config.yaml")
    user = app_config.users[0]

    result = run_workflow_for_user(
        app_config=app_config,
        user=user,
        source_registry=SourceRegistry(),
    )

    repo = SqliteRepository(db_path=str(tmp_path / "test.db"))
    repo.save_workflow_run(result)
    rows = repo.list_recent_runs(limit=5)

    assert len(rows) == 1
    assert rows[0]["user_id"] == user.user_id
    assert int(rows[0]["total_candidates"]) >= 0
