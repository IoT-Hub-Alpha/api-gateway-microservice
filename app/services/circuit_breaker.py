import logging
import time
from enum import Enum
from typing import Dict

from app.core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = None,
        recovery_timeout: int = None,
    ):
        self.failure_threshold = (
            failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.recovery_timeout = (
            recovery_timeout or settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        )

        # State per service: {service_name: {state, failures, last_failure_time}}
        self._circuits: Dict[str, dict] = {}

    def _get_circuit(self, service: str) -> dict:
        """Get or create circuit state for a service."""
        if service not in self._circuits:
            self._circuits[service] = {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "last_failure_time": None,
            }
        return self._circuits[service]

    def can_execute(self, service: str) -> bool:
        """Check if request can proceed."""
        circuit = self._get_circuit(service)

        if circuit["state"] == CircuitState.CLOSED:
            return True

        if circuit["state"] == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._should_attempt_recovery(circuit):
                circuit["state"] = CircuitState.HALF_OPEN
                logger.info(f"Circuit for {service} is now HALF_OPEN")
                return True
            return False

        if circuit["state"] == CircuitState.HALF_OPEN:
            # Allow one request to test
            return True

        return False

    def _should_attempt_recovery(self, circuit: dict) -> bool:
        """Check if enough time has passed to try recovery."""
        if circuit["last_failure_time"] is None:
            return True
        elapsed = time.time() - circuit["last_failure_time"]
        return elapsed >= self.recovery_timeout

    def record_success(self, service: str) -> None:
        """Record successful request."""
        circuit = self._get_circuit(service)

        if circuit["state"] == CircuitState.HALF_OPEN:
            # Service recovered, close the circuit
            circuit["state"] = CircuitState.CLOSED
            circuit["failures"] = 0
            circuit["last_failure_time"] = None
            logger.info(f"Circuit for {service} is now CLOSED")

    def record_failure(self, service: str) -> None:
        """Record failed request."""
        circuit = self._get_circuit(service)
        circuit["failures"] += 1
        circuit["last_failure_time"] = time.time()

        if circuit["state"] == CircuitState.HALF_OPEN:
            # Test request failed, reopen circuit
            circuit["state"] = CircuitState.OPEN
            logger.warning(f"Circuit for {service} is back to OPEN")

        elif circuit["state"] == CircuitState.CLOSED:
            if circuit["failures"] >= self.failure_threshold:
                circuit["state"] = CircuitState.OPEN
                logger.warning(
                    f"Circuit for {service} is now OPEN after {circuit['failures']} failures"
                )

    def get_state(self, service: str) -> CircuitState:
        """Get current circuit state for a service."""
        return self._get_circuit(service)["state"]


# Global instance
circuit_breaker = CircuitBreaker()
