import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._enabled = settings.RATE_LIMIT_ENABLED
        self._requests = settings.RATE_LIMIT_REQUESTS
        self._window = settings.RATE_LIMIT_WINDOW

    def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
            )
        return self._client

    def is_allowed(self, client_id: str) -> tuple[bool, dict]:
        """
        Check if request is allowed for the given client.

        Returns:
            tuple: (is_allowed, info_dict)
            info_dict contains: limit, remaining, reset_in
        """
        if not self._enabled:
            return True, {"limit": 0, "remaining": 0, "reset_in": 0}

        key = f"ratelimit:{client_id}"

        try:
            client = self._get_client()

            # Increment counter
            current = client.incr(key)

            # Set expiry on first request
            if current == 1:
                client.expire(key, self._window)

            # Get TTL for reset info
            ttl = client.ttl(key)
            if ttl < 0:
                ttl = self._window

            remaining = max(0, self._requests - current)
            is_allowed = current <= self._requests

            if not is_allowed:
                logger.warning(f"Rate limit exceeded for {client_id}")

            return is_allowed, {
                "limit": self._requests,
                "remaining": remaining,
                "reset_in": ttl,
            }

        except redis.ConnectionError as e:
            # If Redis is down, allow request (fail open)
            logger.error(f"Redis connection error: {e}")
            return True, {"limit": 0, "remaining": 0, "reset_in": 0}

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


# Global instance
rate_limiter = RateLimiter()
