from __future__ import annotations

import argparse
import json

from core.config import get_user_config, load_config
from core.diagnostics import run_diagnostics
from core.database.factory import create_repository
from core.scheduler.service import run_scheduler_loop
from core.tools.sources.registry import SourceRegistry
from core.workflow import run_workflow_for_user


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MAS-PaperHelper skeleton CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_once = sub.add_parser("run-once", help="Run workflow once for a user")
    run_once.add_argument("--user-id", required=True)

    schedule = sub.add_parser("schedule", help="Start scheduler loop")
    schedule.add_argument("--interval-seconds", type=int, default=300)

    sub.add_parser("doctor", help="Run connectivity and config diagnostics")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    app_config = load_config()
    repository = create_repository(app_config)

    if args.command == "run-once":
        user = get_user_config(app_config, args.user_id)
        result = run_workflow_for_user(
            app_config=app_config,
            user=user,
            source_registry=SourceRegistry(),
        )
        repository.save_workflow_run(result)
        print(
            f"[run-once] user={result.user_id} total={result.total_candidates} "
            f"kept={result.kept_candidates} threshold={result.threshold} "
            f"summaries={len(result.summaries)} sources={','.join(result.sources_used)}"
        )
        return

    if args.command == "schedule":
        run_scheduler_loop(app_config=app_config, interval_seconds=args.interval_seconds)
        return

    if args.command == "doctor":
        report = run_diagnostics(app_config)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
