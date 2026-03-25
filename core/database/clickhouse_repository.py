from __future__ import annotations

from core.models import WorkflowResult


class ClickHouseRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def save_workflow_run(self, result: WorkflowResult) -> None:
        try:
            import clickhouse_connect  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "clickhouse-connect is required for ClickHouseRepository"
            ) from exc

        client = clickhouse_connect.get_client(dsn=self.dsn)
        client.command(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                user_id String,
                total_candidates UInt32,
                kept_candidates UInt32,
                threshold Float32,
                sources_used String,
                summary_count UInt32,
                created_at DateTime DEFAULT now()
            ) ENGINE = MergeTree ORDER BY (user_id, created_at)
            """
        )
        client.insert(
            "workflow_runs",
            [
                [
                    result.user_id,
                    result.total_candidates,
                    result.kept_candidates,
                    result.threshold,
                    ",".join(result.sources_used),
                    len(result.summaries),
                ]
            ],
            column_names=[
                "user_id",
                "total_candidates",
                "kept_candidates",
                "threshold",
                "sources_used",
                "summary_count",
            ],
        )

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, str | int | float]]:
        try:
            import clickhouse_connect  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "clickhouse-connect is required for ClickHouseRepository"
            ) from exc

        client = clickhouse_connect.get_client(dsn=self.dsn)
        rows = client.query(
            """
            SELECT user_id, total_candidates, kept_candidates, threshold, sources_used, summary_count, created_at
            FROM workflow_runs
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            parameters={"limit": limit},
        ).result_rows

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
                    "created_at": str(row[6]),
                }
            )
        return items

    def get_latest_run_result(self, user_id: str | None = None) -> dict | None:
        """Get the latest workflow run result for a user (ClickHouse implementation)."""
        try:
            import clickhouse_connect  # type: ignore
        except Exception:  # pragma: no cover - optional dependency
            return None

        client = clickhouse_connect.get_client(dsn=self.dsn)

        where_clause = "WHERE 1=1"
        params: dict = {}
        if user_id:
            where_clause = "WHERE user_id = %(user_id)s"
            params["user_id"] = user_id

        row = client.query(
            f"""
            SELECT user_id, total_candidates, kept_candidates, threshold, sources_used, summary_count, created_at
            FROM workflow_runs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters=params,
        ).result_rows

        if not row:
            return None

        return {
            "user_id": row[0][0],
            "total_candidates": row[0][1],
            "kept_candidates": row[0][2],
            "threshold": row[0][3],
            "sources_used": row[0][4].split(",") if row[0][4] else [],
            "summaries": [],  # ClickHouse implementation doesn't store full summaries yet
            "created_at": str(row[0][6]),
        }
