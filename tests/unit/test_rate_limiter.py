from unittest.mock import MagicMock, patch

import pytest
import redis


class TestRateLimiter:
    @pytest.fixture
    def rate_limiter(self, mock_redis):
        with patch("app.services.rate_limiter.redis.from_url", return_value=mock_redis):
            with patch("app.services.rate_limiter.settings") as mock_settings:
                mock_settings.RATE_LIMIT_ENABLED = True
                mock_settings.RATE_LIMIT_REQUESTS = 100
                mock_settings.RATE_LIMIT_WINDOW = 60
                mock_settings.REDIS_URL = "redis://localhost:6379/0"
                mock_settings.REDIS_PASSWORD = ""

                from app.services.rate_limiter import RateLimiter

                limiter = RateLimiter()
                limiter._client = mock_redis
                yield limiter

    def test_first_request_allowed(self, rate_limiter, mock_redis):
        mock_redis.incr.return_value = 1
        mock_redis.ttl.return_value = 60

        is_allowed, info = rate_limiter.is_allowed("127.0.0.1")

        assert is_allowed is True
        assert info["remaining"] == 99  # 100 - 1
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_request_at_limit_allowed(self, rate_limiter, mock_redis):
        mock_redis.incr.return_value = 100  # At limit
        mock_redis.ttl.return_value = 30

        is_allowed, info = rate_limiter.is_allowed("127.0.0.1")

        assert is_allowed is True
        assert info["remaining"] == 0

    def test_request_over_limit_rejected(self, rate_limiter, mock_redis):
        mock_redis.incr.return_value = 101  # Over limit
        mock_redis.ttl.return_value = 25

        is_allowed, info = rate_limiter.is_allowed("127.0.0.1")

        assert is_allowed is False
        assert info["remaining"] == 0
        assert info["reset_in"] == 25

    def test_redis_connection_error_allows_request(self, rate_limiter, mock_redis):
        mock_redis.incr.side_effect = redis.ConnectionError("Connection refused")

        is_allowed, info = rate_limiter.is_allowed("127.0.0.1")

        # Fail open - allow request when Redis is down
        assert is_allowed is True

    def test_rate_limit_disabled(self, mock_redis):
        with patch("app.services.rate_limiter.redis.from_url", return_value=mock_redis):
            with patch("app.services.rate_limiter.settings") as mock_settings:
                mock_settings.RATE_LIMIT_ENABLED = False
                mock_settings.RATE_LIMIT_REQUESTS = 100
                mock_settings.RATE_LIMIT_WINDOW = 60

                from app.services.rate_limiter import RateLimiter

                limiter = RateLimiter()
                is_allowed, _ = limiter.is_allowed("127.0.0.1")

                assert is_allowed is True
                mock_redis.incr.assert_not_called()
