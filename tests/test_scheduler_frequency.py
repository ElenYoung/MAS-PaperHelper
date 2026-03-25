from datetime import UTC, datetime, timedelta

from core.scheduler.service import _should_run


def test_should_run_daily() -> None:
    last = {"u1": datetime.now(UTC) - timedelta(hours=23)}
    assert _should_run("u1", "daily", last) is False

    last = {"u1": datetime.now(UTC) - timedelta(days=1, minutes=1)}
    assert _should_run("u1", "daily", last) is True
