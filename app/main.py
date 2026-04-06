import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from iot_logging import FastAPIRequestContextMiddleware, StructuredJsonFormatter

from app.api.router import router as api_router
from app.core.config import settings
from app.services.circuit_breaker import circuit_breaker
from app.services.rate_limiter import rate_limiter
from app.services.proxy import proxy_request, proxy_websocket

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging with structured JSON formatter."""
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
    for handler in logging.root.handlers:
        handler.setFormatter(StructuredJsonFormatter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} on {settings.HOST}:{settings.PORT}")
    yield
    # Shutdown
    rate_limiter.close()
    circuit_breaker.close()
    logger.info(f"Shutting down {settings.APP_NAME}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="API Gateway",
        description="Central entry point for all backend microservices",
        version="1.0.0",
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    # Request context middleware (auto-injects request_id, method, path, logs duration)
    app.add_middleware(FastAPIRequestContextMiddleware)

    # Health check endpoints at root level (for infrastructure tools)
    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    # Include API router with /api prefix
    app.include_router(api_router, prefix="/api")

    # HTTP proxy for /ws/demo and other static content at root level
    @app.api_route("/ws/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def ws_http_proxy(path: str, request: Request):
        """Proxy HTTP requests to websocket-service."""
        return await proxy_request("websocket-service", path, request)

    # WebSocket at root level /ws
    @app.websocket("/ws/{path:path}")
    async def websocket_proxy(websocket: WebSocket, path: str):
        """Proxy WebSocket connections to websocket-service at /ws/telemetry/"""
        await proxy_websocket(websocket, path)

    return app


app = create_app()
