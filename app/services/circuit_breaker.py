import logging
import time
from enum import Enum
from typing import Optional

import redis

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
        self._client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
            )
        return self._client

    def _get_key(self, service: str) -> str:
        """Get Redis key for service circuit."""
        return f"circuit:{service}"

    def _get_circuit(self, service: str) -> dict:
        """Get circuit state from Redis."""
        try:
            client = self._get_client()
            key = self._get_key(service)
            data = client.hgetall(key)

            if not data:
                return {
                    "state": CircuitState.CLOSED,
                    "failures": 0,
                    "last_failure_time": None,
                }

            return {
                "state": CircuitState(data.get("state", "closed")),
                "failures": int(data.get("failures", 0)),
                "last_failure_time": (
                    float(data["last_failure_time"])
                    if data.get("last_failure_time")
                    else None
                ),
            }
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            return {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "last_failure_time": None,
            }

    def _set_circuit(self, service: str, circuit: dict) -> None:
        """Save circuit state to Redis."""
        try:
            client = self._get_client()
            key = self._get_key(service)
            data = {
                "state": circuit["state"].value,
                "failures": str(circuit["failures"]),
                "last_failure_time": str(circuit["last_failure_time"] or ""),
            }
            client.hset(key, mapping=data)
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")

    def can_execute(self, service: str) -> bool:
        """Check if request can proceed."""
        circuit = self._get_circuit(service)

        if circuit["state"] == CircuitState.CLOSED:
            return True

        if circuit["state"] == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._should_attempt_recovery(circuit):
                circuit["state"] = CircuitState.HALF_OPEN
                self._set_circuit(service, circuit)
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
            self._set_circuit(service, circuit)
            logger.info(f"Circuit for {service} is now CLOSED")

    def record_failure(self, service: str) -> None:
        """Record failed request."""
        circuit = self._get_circuit(service)
        circuit["failures"] += 1
        circuit["last_failure_time"] = time.time()

        if circuit["state"] == CircuitState.HALF_OPEN:
            # Test request failed, reopen circuit
            circuit["state"] = CircuitState.OPEN
            self._set_circuit(service, circuit)
            logger.warning(f"Circuit for {service} is back to OPEN")

        elif circuit["state"] == CircuitState.CLOSED:
            if circuit["failures"] >= self.failure_threshold:
                circuit["state"] = CircuitState.OPEN
                logger.warning(
                    f"Circuit for {service} is now OPEN after {circuit['failures']} failures"
                )
            self._set_circuit(service, circuit)

    def get_state(self, service: str) -> CircuitState:
        """Get current circuit state for a service."""
        return self._get_circuit(service)["state"]

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


# Global instance
circuit_breaker = CircuitBreaker()
