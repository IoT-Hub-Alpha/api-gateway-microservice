import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = MagicMock()
    mock.incr.return_value = 1
    mock.expire.return_value = True
    mock.ttl.return_value = 60
    mock.hgetall.return_value = {}
    mock.hset.return_value = True
    return mock


@pytest.fixture
def client(mock_redis):
    """FastAPI test client with mocked Redis."""
    with patch("app.services.rate_limiter.redis.from_url", return_value=mock_redis):
        with patch(
            "app.services.circuit_breaker.redis.from_url", return_value=mock_redis
        ):
            from app.main import app

            with TestClient(app) as test_client:
                yield test_client
