# HOVERTRANSLATE skeleton file
from __future__ import annotations

import threading
import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Allows failure after 5 failures in 60 seconds, then opens for 30 seconds."""

    def __init__(
        self,
        failure_threshold: int = 5,
        failure_window_s: int = 60,
        recovery_time_s: int = 30,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._failure_window_s = failure_window_s
        self._recovery_time_s = recovery_time_s
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._failures: list[float] = []
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def allow_request(self) -> bool:
        with self._lock:
            self._maybe_half_open()

            if self._state is CircuitState.CLOSED:
                return True

            if self._state is CircuitState.HALF_OPEN:
                return True

            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()
            self._opened_at = None
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        now = time.monotonic()

        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._trip(now)
                return

            self._failures.append(now)
            self._prune_old_failures(now)

            if len(self._failures) >= self._failure_threshold:
                self._trip(now)

    def _trip(self, now: float) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = now
        self._failures.clear()

    def _maybe_half_open(self) -> None:
        if self._state is not CircuitState.OPEN:
            return

        if self._opened_at is None:
            self._state = CircuitState.CLOSED
            return

        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self._recovery_time_s:
            self._state = CircuitState.HALF_OPEN

    def _prune_old_failures(self, now: float) -> None:
        cutoff = now - self._failure_window_s
        self._failures = [
            timestamp
            for timestamp in self._failures
            if timestamp >= cutoff
        ]