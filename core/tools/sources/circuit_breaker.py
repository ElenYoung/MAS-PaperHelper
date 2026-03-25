from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: datetime | None = None


class InMemoryCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 120) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[str, CircuitState] = {}

    def allow(self, source_name: str) -> bool:
        state = self._states.get(source_name)
        if state is None or state.opened_until is None:
            return True
        return datetime.now(UTC) >= state.opened_until

    def record_success(self, source_name: str) -> None:
        self._states[source_name] = CircuitState(failures=0, opened_until=None)

    def record_failure(self, source_name: str) -> None:
        state = self._states.get(source_name, CircuitState())
        state.failures += 1
        if state.failures >= self.failure_threshold:
            state.opened_until = datetime.now(UTC) + timedelta(seconds=self.cooldown_seconds)
        self._states[source_name] = state
