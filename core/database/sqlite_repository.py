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

    def get_latest_run_result(self, user_id: str | None = None) -> dict | None:
        """Get the latest workflow run result with summaries for a user (or any user if None)."""
        # Get latest workflow run
        sql = """
            SELECT id, user_id, total_candidates, kept_candidates, threshold,
                   sources_used, summary_count, created_at
            FROM workflow_runs
            WHERE 1=1
        """
        params: list = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        sql += " ORDER BY id DESC LIMIT 1"

        row = self._conn.execute(sql, params).fetchone()
        if not row:
            return None

        run_id, run_user_id, total, kept, threshold, sources, summary_count, created_at = row

        # Get summaries for this run from paper_history (by user and recent timestamp)
        # We get papers saved around the same time as the run
        summaries_sql = """
            SELECT title, source, score, published_at, paper_url, abstract,
                   research_problem, innovation_summary, matched_interests
            FROM paper_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        summary_rows = self._conn.execute(summaries_sql, (run_user_id, summary_count)).fetchall()

        summaries = []
        for srow in summary_rows:
            from datetime import datetime
            pub_at = srow[3]
            if pub_at and isinstance(pub_at, str):
                try:
                    pub_at = datetime.fromisoformat(pub_at)
                except ValueError:
                    pub_at = None
            summaries.append({
                "title": srow[0],
                "source": srow[1],
                "score": srow[2],
                "published_at": pub_at,
                "paper_url": srow[4],
                "abstract": srow[5],
                "research_problem": srow[6],
                "innovation_summary": srow[7],
                "matched_interests": srow[8].split(",") if srow[8] else [],
            })

        return {
            "user_id": run_user_id,
            "total_candidates": total,
            "kept_candidates": kept,
            "threshold": threshold,
            "sources_used": sources.split(",") if sources else [],
            "summaries": summaries,
            "created_at": created_at,
        }
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
