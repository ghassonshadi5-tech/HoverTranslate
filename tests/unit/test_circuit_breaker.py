from __future__ import annotations

from hovertranslate.translation.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)


def test_circuit_opens_after_threshold() -> None:
    breaker = CircuitBreaker(
        failure_threshold=5,
        failure_window_s=60,
        recovery_time_s=30,
    )

    for _ in range(5):
        breaker.record_failure()

    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False


def test_circuit_closes_after_success() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2,
        failure_window_s=60,
        recovery_time_s=30,
    )

    breaker.record_failure()
    breaker.record_success()

    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True