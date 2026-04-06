import asyncio
import logging

import httpx
import websockets
from fastapi import Request, Response, WebSocket

from app.core.config import settings, get_service_url
from app.services.circuit_breaker import circuit_breaker
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


async def proxy_request(
    service: str,
    path: str,
    request: Request,
) -> Response:
    """
    Forward request to backend service.
    """
    # Check rate limit
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rate_info = rate_limiter.is_allowed(client_ip)

    if not is_allowed:
        return Response(
            content='{"detail": "Too many requests"}',
            status_code=429,
            media_type="application/json",
            headers={
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "Retry-After": str(rate_info["reset_in"]),
            },
        )

    try:
        target_url = get_service_url(service)
    except ValueError:
        return Response(
            content=f'{{"detail": "Unknown service: {service}"}}',
            status_code=404,
            media_type="application/json",
        )

    # Check circuit breaker
    if not circuit_breaker.can_execute(service):
        logger.warning(f"Circuit OPEN for {service}, rejecting request")
        return Response(
            content=f'{{"detail": "Service temporarily unavailable: {service}"}}',
            status_code=503,
            media_type="application/json",
        )

    # Build full URL
    url = f"{target_url}/{path}"
    if request.query_params:
        url = f"{url}?{request.query_params}"

    # Get request body
    body = await request.body()

    # Prepare headers (exclude hop-by-hop headers)
    excluded_headers = {"host", "connection", "keep-alive", "transfer-encoding"}
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in excluded_headers
    }

    # Add forwarding headers
    client_host = request.client.host if request.client else "unknown"
    headers["X-Forwarded-For"] = client_host
    headers["X-Forwarded-Host"] = request.headers.get("host", "")

    logger.info(f"Proxying {request.method} /{service}/{path} -> {url}")

    try:
        async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )

        # Success - record it
        circuit_breaker.record_success(service)

        # Return response from backend
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )

    except httpx.ConnectError:
        circuit_breaker.record_failure(service)
        logger.error(f"Cannot connect to {service} at {target_url}")
        return Response(
            content=f'{{"detail": "Service unavailable: {service}"}}',
            status_code=503,
            media_type="application/json",
        )
    except httpx.TimeoutException:
        circuit_breaker.record_failure(service)
        logger.error(f"Timeout connecting to {service} at {target_url}")
        return Response(
            content=f'{{"detail": "Service timeout: {service}"}}',
            status_code=504,
            media_type="application/json",
        )


async def proxy_websocket(websocket: WebSocket, path: str) -> None:
    """
    Proxy WebSocket connections to websocket-service.

    Routes /ws/{path} requests to the websocket-service backend.

    Example:
        ws://localhost:8000/ws/telemetry/?token=xyz -> ws://websocket-service:8006/ws/telemetry/?token=xyz
    """
    service = "websocket-service"

    try:
        target_url = get_service_url(service)
    except ValueError:
        await websocket.close(code=4004, reason="Unknown service")
        return

    # Build WebSocket URL (convert http to ws, https to wss)
    ws_url = target_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/{path}"

    # Append query string if present
    query_string = websocket.scope.get("query_string", b"").decode()
    if query_string:
        ws_url = f"{ws_url}?{query_string}"

    logger.info(f"Proxying WebSocket /ws/{path} -> {ws_url}")

    try:
        # Accept the WebSocket connection from client
        await websocket.accept()

        # Connect to backend WebSocket
        async with websockets.connect(ws_url) as backend_ws:
            # Create two concurrent tasks to forward messages both ways
            async def client_to_backend():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await backend_ws.send(data)
                except Exception as e:
                    logger.error(f"Client -> Backend error: {e}")

            async def backend_to_client():
                try:
                    while True:
                        data = await backend_ws.recv()
                        await websocket.send_text(data)
                except Exception as e:
                    logger.error(f"Backend -> Client error: {e}")

            # Run both concurrently
            await asyncio.gather(client_to_backend(), backend_to_client())

    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
