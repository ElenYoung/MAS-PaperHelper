from __future__ import annotations

from core.config import AppConfig
from core.database.clickhouse_repository import ClickHouseRepository
from core.database.sqlite_repository import SqliteRepository


def create_repository(app_config: AppConfig) -> SqliteRepository | ClickHouseRepository:
    backend = app_config.database.backend.lower()
    if backend == "clickhouse":
        if not app_config.database.clickhouse_dsn:
            raise ValueError("database.clickhouse_dsn is required when backend=clickhouse")
        return ClickHouseRepository(dsn=app_config.database.clickhouse_dsn)

    return SqliteRepository(db_path=app_config.database.sqlite_path)
