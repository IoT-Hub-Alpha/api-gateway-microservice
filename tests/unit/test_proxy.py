from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestProxyEndpoints:
    def test_unknown_service_returns_404(self, client):
        response = client.get("/api/v1/unknown-service/test")
        assert response.status_code == 404
        assert "Unknown service" in response.json()["detail"]

    def test_proxy_forwards_request(self, client, mock_redis):
        mock_response = MagicMock()
        mock_response.content = b'{"data": "test"}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("app.services.proxy.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/devices/test")

            assert response.status_code == 200
            assert response.json() == {"data": "test"}

    def test_proxy_returns_503_on_connection_error(self, client, mock_redis):
        with patch("app.services.proxy.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/devices/test")

            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"]

    def test_proxy_returns_504_on_timeout(self, client, mock_redis):
        with patch("app.services.proxy.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/devices/test")

            assert response.status_code == 504
            assert "timeout" in response.json()["detail"]

    def test_rate_limit_returns_429(self, client, mock_redis):
        # Simulate rate limit exceeded
        mock_redis.incr.return_value = 101  # Over default limit of 100
        mock_redis.ttl.return_value = 30

        response = client.get("/api/v1/devices/test")

        assert response.status_code == 429
        assert "Too many requests" in response.json()["detail"]
        assert "Retry-After" in response.headers

    def test_circuit_open_returns_503(self, client, mock_redis):
        import time

        # Simulate open circuit
        mock_redis.hgetall.return_value = {
            "state": "open",
            "failures": "5",
            "last_failure_time": str(time.time()),
        }

        response = client.get("/api/v1/devices/test")

        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]

    def test_proxy_preserves_query_params(self, client, mock_redis):
        mock_response = MagicMock()
        mock_response.content = b'{"data": "test"}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("app.services.proxy.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/devices/test?foo=bar&baz=123")

            # Check that the URL included query params
            call_args = mock_instance.request.call_args
            assert "foo=bar" in call_args[1]["url"]
            assert "baz=123" in call_args[1]["url"]

    def test_proxy_forwards_post_with_body(self, client, mock_redis):
        mock_response = MagicMock()
        mock_response.content = b'{"created": true}'
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}

        with patch("app.services.proxy.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            response = client.post(
                "/api/v1/devices/create",
                json={"name": "test-device"},
            )

            assert response.status_code == 201
            call_args = mock_instance.request.call_args
            assert call_args[1]["method"] == "POST"
