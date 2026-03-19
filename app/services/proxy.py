import logging

import httpx
from fastapi import Request, Response

from app.core.config import settings, get_service_url
from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


async def proxy_request(
    service: str,
    path: str,
    request: Request,
) -> Response:
    """
    Forward request to backend service.
    """
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
