import time
from unittest.mock import MagicMock, patch

import pytest
import redis

from app.services.circuit_breaker import CircuitState


class TestCircuitBreaker:
    @pytest.fixture
    def circuit_breaker(self, mock_redis):
        with patch(
            "app.services.circuit_breaker.redis.from_url", return_value=mock_redis
        ):
            from app.services.circuit_breaker import CircuitBreaker

            cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
            cb._client = mock_redis
            return cb

    def test_closed_circuit_allows_execution(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {}  # No state = CLOSED

        assert circuit_breaker.can_execute("test-service") is True

    def test_open_circuit_blocks_execution(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {
            "state": "open",
            "failures": "3",
            "last_failure_time": str(time.time()),  # Recent failure
        }

        assert circuit_breaker.can_execute("test-service") is False

    def test_open_circuit_transitions_to_half_open_after_timeout(
        self, circuit_breaker, mock_redis
    ):
        mock_redis.hgetall.return_value = {
            "state": "open",
            "failures": "3",
            "last_failure_time": str(time.time() - 15),  # 15 seconds ago
        }

        # Should transition to HALF_OPEN and allow
        assert circuit_breaker.can_execute("test-service") is True
        mock_redis.hset.assert_called()  # State was updated

    def test_half_open_allows_execution(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {
            "state": "half_open",
            "failures": "3",
            "last_failure_time": str(time.time() - 15),
        }

        assert circuit_breaker.can_execute("test-service") is True

    def test_record_failure_increments_count(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {
            "state": "closed",
            "failures": "1",
            "last_failure_time": "",
        }

        circuit_breaker.record_failure("test-service")

        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["failures"] == "2"

    def test_record_failure_opens_circuit_at_threshold(
        self, circuit_breaker, mock_redis
    ):
        mock_redis.hgetall.return_value = {
            "state": "closed",
            "failures": "2",  # One more will hit threshold of 3
            "last_failure_time": "",
        }

        circuit_breaker.record_failure("test-service")

        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["state"] == "open"

    def test_record_success_closes_half_open_circuit(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {
            "state": "half_open",
            "failures": "3",
            "last_failure_time": str(time.time() - 15),
        }

        circuit_breaker.record_success("test-service")

        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["state"] == "closed"
        assert call_args[1]["mapping"]["failures"] == "0"

    def test_record_failure_reopens_half_open_circuit(
        self, circuit_breaker, mock_redis
    ):
        mock_redis.hgetall.return_value = {
            "state": "half_open",
            "failures": "3",
            "last_failure_time": str(time.time() - 15),
        }

        circuit_breaker.record_failure("test-service")

        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["state"] == "open"

    def test_redis_connection_error_allows_execution(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.side_effect = redis.ConnectionError("Connection refused")

        # Fail open - allow execution when Redis is down
        assert circuit_breaker.can_execute("test-service") is True

    def test_get_state_returns_current_state(self, circuit_breaker, mock_redis):
        mock_redis.hgetall.return_value = {
            "state": "open",
            "failures": "5",
            "last_failure_time": str(time.time()),
        }

        state = circuit_breaker.get_state("test-service")

        assert state == CircuitState.OPEN
