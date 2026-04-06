from fastapi import APIRouter, Request

from app.services.proxy import proxy_request

router = APIRouter()


@router.api_route(
    "/{version}/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy(version: str, service: str, path: str, request: Request):
    """
    Proxy requests to backend services.

    Gateway adds /api/ prefix. Services define /{version}/{service}/{endpoint}.

    Examples:
        GET /api/v1/auth/login -> http://auth-service:8005/v1/auth/login
        GET /api/v2/devices/123 -> http://devices-service:8001/v2/devices/123
    """
    full_path = f"{version}/{service}/{path}"
    return await proxy_request(service, full_path, request)
