import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Config(BaseSettings):
    # Application
    APP_NAME: str = os.getenv("APP_NAME", "api-gateway")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Backend Services
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8005")
    DEVICES_SERVICE_URL: str = os.getenv(
        "DEVICES_SERVICE_URL", "http://devices-service:8001"
    )
    TELEMETRY_SERVICE_URL: str = os.getenv(
        "TELEMETRY_SERVICE_URL", "http://telemetry-service:8002"
    )
    RULES_SERVICE_URL: str = os.getenv("RULES_SERVICE_URL", "http://rules-service:8003")
    EVENTS_SERVICE_URL: str = os.getenv(
        "EVENTS_SERVICE_URL", "http://events-service:8004"
    )
    
    NOTIFICATIONS_SERVICE_URL: str = os.getenv("NOTIFICATIONS_SERVICE_URL", "http://notification-api:8015")
    
    USER_SERVICE_URL: str = os.getenv("USER_SERVICE_URL", "http://user-api:8013")

    # Timeouts
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "30"))

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    )
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = int(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30")
    )


settings = Config()

# Backend service registry
BACKEND_SERVICES = {
    "auth": {
        "prefix": "/auth",
        "url": settings.AUTH_SERVICE_URL,
    },
    "devices": {
        "prefix": "/devices",
        "url": settings.DEVICES_SERVICE_URL,
    },
    "telemetry": {
        "prefix": "/telemetry",
        "url": settings.TELEMETRY_SERVICE_URL,
    },
    "rules": {
        "prefix": "/rules",
        "url": settings.RULES_SERVICE_URL,
    },
    "events": {
        "prefix": "/events",
        "url": settings.EVENTS_SERVICE_URL,
    },
    "notifications": {
        "prefix": "/notifications",
        "url": settings.NOTIFICATIONS_SERVICE_URL
    },
    "users": {
        "prefix": "/users",
        "url": settings.USER_SERVICE_URL
    }
}


def get_service_url(service_name: str) -> str:
    service = BACKEND_SERVICES.get(service_name)
    if not service:
        raise ValueError(f"Unknown service: {service_name}")
    return service["url"]
