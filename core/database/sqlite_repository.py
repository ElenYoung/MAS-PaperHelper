from __future__ import annotations

import sqlite3
from pathlib import Path

from core.models import PaperCandidate, PaperSummary, WorkflowResult


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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_papers (
                user_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                title TEXT NOT NULL,
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, paper_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                score REAL NOT NULL,
                published_at TEXT,
                paper_url TEXT,
                abstract TEXT,
                research_problem TEXT,
                innovation_summary TEXT,
                matched_interests TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, paper_id)
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

    def get_seen_paper_ids(self, user_id: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT paper_id FROM seen_papers WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r[0] for r in rows}

    def mark_papers_seen(self, user_id: str, papers: list[PaperCandidate]) -> None:
        for p in papers:
            if not p.paper_id:
                continue
            self._conn.execute(
                "INSERT OR IGNORE INTO seen_papers(user_id, paper_id, title) VALUES (?, ?, ?)",
                (user_id, p.paper_id, p.title),
            )
        self._conn.commit()

    def save_paper_summaries(self, user_id: str, summaries: list[PaperSummary]) -> None:
        for s in summaries:
            paper_id = s.paper_url or s.title
            self._conn.execute(
                """
                INSERT OR REPLACE INTO paper_history(
                    user_id, paper_id, title, source, score, published_at,
                    paper_url, abstract, research_problem, innovation_summary, matched_interests
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, paper_id, s.title, s.source, s.score,
                    str(s.published_at) if s.published_at else "",
                    s.paper_url, s.abstract, s.research_problem, s.innovation_summary,
                    ",".join(s.matched_interests),
                ),
            )
        self._conn.commit()

    def search_paper_history(
        self, user_id: str | None = None, query: str = "", limit: int = 50
    ) -> list[dict]:
        sql = "SELECT user_id, paper_id, title, source, score, published_at, paper_url, abstract, research_problem, innovation_summary, matched_interests, created_at FROM paper_history WHERE 1=1"
        params: list = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if query.strip():
            sql += " AND (title LIKE ? OR abstract LIKE ?)"
            like = f"%{query.strip()}%"
            params.extend([like, like])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        cols = ["user_id", "paper_id", "title", "source", "score", "published_at", "paper_url", "abstract", "research_problem", "innovation_summary", "matched_interests", "created_at"]
        return [dict(zip(cols, r)) for r in rows]
