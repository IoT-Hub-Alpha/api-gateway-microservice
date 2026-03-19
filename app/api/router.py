from fastapi import APIRouter, Request

from app.services.proxy import proxy_request

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "healthy"}


@router.get("/ready")
async def ready():
    return {"status": "ready"}


@router.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy(service: str, path: str, request: Request):
    """
    Proxy requests to backend services.

    Examples:
        GET /devices/123 -> http://devices-service:8001/123
        POST /auth/login -> http://auth-service:8005/login
    """
    return await proxy_request(service, path, request)
