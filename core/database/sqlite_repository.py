from __future__ import annotations

import sqlite3
from pathlib import Path

from core.models import WorkflowResult


class SqliteRepository:
    def __init__(self, db_path: str = "data/app.db") -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                total_candidates INTEGER NOT NULL,
                kept_candidates INTEGER NOT NULL,
                threshold REAL NOT NULL,
                sources_used TEXT NOT NULL,
                summary_count INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def save_workflow_run(self, result: WorkflowResult) -> None:
        self._conn.execute(
            """
            INSERT INTO workflow_runs(
                user_id, total_candidates, kept_candidates, threshold, sources_used, summary_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result.user_id,
                result.total_candidates,
                result.kept_candidates,
                result.threshold,
                ",".join(result.sources_used),
                len(result.summaries),
            ),
        )
        self._conn.commit()

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, str | int | float]]:
        rows = self._conn.execute(
            """
            SELECT user_id, total_candidates, kept_candidates, threshold, sources_used, summary_count, created_at
            FROM workflow_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        items: list[dict[str, str | int | float]] = []
        for row in rows:
            items.append(
                {
                    "user_id": row[0],
                    "total_candidates": row[1],
                    "kept_candidates": row[2],
                    "threshold": row[3],
                    "sources_used": row[4],
                    "summary_count": row[5],
                    "created_at": row[6],
                }
            )
        return items
