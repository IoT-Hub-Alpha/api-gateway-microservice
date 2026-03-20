# API Gateway Microservice Implementation Plan

## Overview

Create a **FastAPI-based** API Gateway microservice that serves as the central entry point for all backend microservices, handling authentication, routing, rate limiting, and circuit breaking.

**Location:** `/Users/oleksandr/education/soft_serf/microservices/api-gateway-microservice/`
**Port:** 8000
**Framework:** FastAPI (async, lightweight, high-performance)

**Key Decisions:**
- **Framework:** FastAPI (better async support for proxying)
- **Routing:** Placeholder URLs for future microservices
- **JWT:** Local validation using shared secret (no HTTP call to Auth Service)
- **No database:** Stateless gateway, Redis for rate limiting cache only

**Related Tasks:**
- Part 1: API Gateway (this plan) - FastAPI
- Part 2: Auth Service (separate) - Django with admin panel, JWT token generation, user management

**JWT Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│              Shared Environment Variable                         │
│              JWT_SECRET_KEY=shared-secret                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ↓                               ↓
┌───────────────┐               ┌───────────────┐
│ Auth Service  │               │   Gateway     │
│   (Django)    │               │  (FastAPI)    │
│               │               │               │
│ CREATES JWT   │               │ VALIDATES JWT │
│ (login/refresh)│              │ (locally)     │
└───────────────┘               └───────────────┘
```

---

## Project Structure

```
api-gateway-microservice/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py          # API v1 router
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py      # Health/readiness endpoints
│   │           ├── metrics.py     # Prometheus metrics
│   │           └── proxy.py       # Proxy endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── security.py            # JWT validation helpers
│   │   └── logging.py             # Structured JSON logging
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py          # X-Request-ID generation
│   │   ├── logging.py             # Request/response logging
│   │   ├── rate_limiting.py       # Rate limiter
│   │   ├── jwt_auth.py            # JWT authentication
│   │   └── circuit_breaker.py     # Circuit breaker middleware
│   ├── services/
│   │   ├── __init__.py
│   │   ├── proxy.py               # HTTP proxy logic (httpx)
│   │   ├── circuit_breaker.py     # Circuit breaker state machine
│   │   └── rate_limiter.py        # Redis-based rate limiter
│   ├── models/
│   │   └── __init__.py            # (empty - stateless)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py              # Health response schemas
│   │   └── errors.py              # Error response schemas
│   └── db/
│       └── __init__.py            # (empty - no database)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_rate_limiting.py
│   │   ├── test_circuit_breaker.py
│   │   └── test_proxy.py
│   └── integration/
│       └── __init__.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Implementation Steps

### Phase 1: FastAPI Project Setup

1. **Create FastAPI project structure**
   - Initialize project with `app/main.py` entry point
   - Create api/v1 router structure
   - Set up Pydantic settings (`app/core/config.py`)

2. **Configure application**
   - No database (stateless gateway)
   - Redis for rate limiting cache
   - Structured JSON logging
   - CORS via FastAPI middleware

3. **Dependencies** (`requirements.txt`):
   ```
   fastapi==0.111.0
   uvicorn[standard]==0.30.1
   httpx==0.27.0
   redis==5.0.8
   PyJWT==2.8.0
   pydantic-settings==2.3.0
   prometheus-client==0.20.0
   python-json-logger==2.0.7
   ```

4. **Dev dependencies** (`requirements-dev.txt`):
   ```
   pytest==8.2.2
   pytest-asyncio==0.23.7
   pytest-cov==5.0.0
   httpx==0.27.0
   black==24.4.2
   ruff==0.4.8
   ```

### Phase 2: Core Functionality

5. **Health & Metrics endpoints** (`app/api/v1/endpoints/health.py`)
   - `GET /health/` - Liveness check
   - `GET /ready/` - Readiness (checks Redis, downstream services)
   - `GET /metrics/` - Prometheus metrics

6. **Request logging middleware** (`app/middleware/logging.py`)
   - Generate/propagate X-Request-ID
   - Log request start, response status, latency
   - Structured JSON format

### Phase 3: Routing & Proxy

7. **Service registry** (`app/core/config.py`)
   - Configurable backend service URLs via pydantic-settings
   - Placeholder URLs for future microservices
   ```python
   class Settings(BaseSettings):
       # Backend Services
       devices_service_url: str = "http://devices-service:8001"
       telemetry_service_url: str = "http://telemetry-service:8002"
       rules_service_url: str = "http://rules-service:8003"
       events_service_url: str = "http://events-service:8004"
       auth_service_url: str = "http://auth-service:8005"

       # Service timeouts
       default_timeout: int = 30
       auth_timeout: int = 10

   BACKEND_SERVICES = {
       "devices": {"prefix": "/api/v1/devices"},
       "telemetry": {"prefix": "/api/v1/telemetry"},
       "rules": {"prefix": "/api/v1/rules"},
       "events": {"prefix": "/api/v1/events"},
       "auth": {"prefix": "/api/v1/auth"},
   }
   ```

8. **Proxy service** (`app/services/proxy.py`)
   - Use `httpx.AsyncClient` for async HTTP forwarding
   - Preserve headers, body, query params
   - Add `X-Request-ID`, `X-Forwarded-For`, `X-User-ID`
   - Return `503 Service Unavailable` if backend not reachable

9. **Proxy endpoints** (`app/api/v1/endpoints/proxy.py`)
   - Catch-all route for `/api/v1/{service}/{path:path}`
   - Route to appropriate backend based on service name

### Phase 4: Rate Limiting

10. **Rate limiter service** (`app/services/rate_limiter.py`)
    - Redis backend with sliding window algorithm
    - Support per-IP, per-user (JWT user_id), per-API-key
    - Configurable limits per endpoint pattern

11. **Rate limiting middleware** (`app/middleware/rate_limiting.py`)
    - Extract client identifier (IP, user_id, API key)
    - Check rate limit via rate limiter service
    - Return `429 Too Many Requests` with `Retry-After` header

### Phase 5: JWT Authentication

12. **JWT security helpers** (`app/core/security.py`)
    - Local JWT validation using shared `JWT_SECRET_KEY`
    - No HTTP call to Auth Service needed
    - Decode token, verify signature, check expiry
    - Extract user_id, roles from token payload
    ```python
    def validate_token(token: str) -> dict:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return {"user_id": payload["sub"], "roles": payload["roles"]}
    ```

13. **JWT middleware** (`app/middleware/jwt_auth.py`)
    - Extract token from `Authorization: Bearer <token>` header
    - Validate locally using `app/core/security.py`
    - Configurable via `JWT_VALIDATION_ENABLED` (default: false for initial testing)
    - When enabled:
      - Valid token → inject `X-User-ID`, `X-User-Roles` headers for downstream
      - Invalid/expired token → return `401 Unauthorized`
      - Missing token → configurable (allow anonymous or reject)

14. **Public routes configuration**
    - Some routes don't require auth (health, metrics, login, register)
    - Configure list of public path patterns in settings

### Phase 6: Circuit Breaker

15. **Circuit breaker service** (`app/services/circuit_breaker.py`)
    - States: CLOSED, OPEN, HALF_OPEN
    - Configurable: failure threshold, recovery timeout, half-open requests
    - Per-service circuit state (in-memory or Redis)

16. **Circuit breaker middleware** (`app/middleware/circuit_breaker.py`)
    - Check circuit state before proxying
    - Track failures and successes
    - Return `503 Service Unavailable` when circuit is OPEN

### Phase 7: CORS & API Versioning

17. **CORS configuration** (`app/main.py`)
    - Use FastAPI's `CORSMiddleware`
    - Configurable allowed origins, methods, headers via settings

18. **API versioning**
    - URL-based: `/api/v1/`, `/api/v2/`
    - Routers organized by version: `app/api/v1/`, `app/api/v2/`
    - Version extracted from path for routing decisions

---

## Key Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `app/main.py` | Create | FastAPI app entry point |
| `app/core/config.py` | Create | Pydantic settings |
| `app/core/logging.py` | Create | Structured JSON logging |
| `app/api/v1/router.py` | Create | API v1 router |
| `app/api/v1/endpoints/health.py` | Create | Health/metrics endpoints |
| `app/api/v1/endpoints/proxy.py` | Create | Proxy endpoints |
| `app/middleware/request_id.py` | Create | X-Request-ID middleware |
| `app/middleware/logging.py` | Create | Request/response logging |
| `app/middleware/rate_limiting.py` | Create | Rate limiter middleware |
| `app/middleware/jwt_auth.py` | Create | JWT validation middleware |
| `app/middleware/circuit_breaker.py` | Create | Circuit breaker middleware |
| `app/core/security.py` | Create | JWT validation helpers |
| `app/services/proxy.py` | Create | HTTP proxy logic (httpx) |
| `app/services/rate_limiter.py` | Create | Redis rate limiter |
| `app/services/circuit_breaker.py` | Create | Circuit breaker state machine |
| `app/schemas/health.py` | Create | Health response schemas |
| `app/schemas/errors.py` | Create | Error response schemas |
| `tests/conftest.py` | Create | Pytest fixtures |
| `requirements.txt` | Modify | Add FastAPI dependencies |
| `Dockerfile` | Modify | Update for uvicorn |
| `.env.example` | Modify | Add all config vars |

---

## Configuration (.env.example)

```env
# Application
APP_NAME=api-gateway
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Redis (for rate limiting cache)
REDIS_URL=redis://localhost:6379/0

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_REQUESTS=100
RATE_LIMIT_DEFAULT_WINDOW_SECONDS=60

# JWT Authentication (local validation with shared secret)
JWT_VALIDATION_ENABLED=false
JWT_SECRET_KEY=your-256-bit-secret-shared-with-auth-service
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15

# Public routes (no auth required) - comma separated
PUBLIC_ROUTES=/health,/ready,/metrics,/api/v1/auth/login,/api/v1/auth/register

# Auth Service (for proxying login/register/refresh requests)
AUTH_SERVICE_URL=http://auth-service:8005

# Backend Services (placeholder URLs - update as services are deployed)
DEVICES_SERVICE_URL=http://devices-service:8001
TELEMETRY_SERVICE_URL=http://telemetry-service:8002
RULES_SERVICE_URL=http://rules-service:8003
EVENTS_SERVICE_URL=http://events-service:8004

# Service Timeouts
DEFAULT_TIMEOUT_SECONDS=30
AUTH_TIMEOUT_SECONDS=10

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS=30
CIRCUIT_BREAKER_HALF_OPEN_REQUESTS=3

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
CORS_ALLOW_CREDENTIALS=true
```

---

## Verification

1. **Run tests:**
   ```bash
   cd api-gateway-microservice
   pip install -r requirements.txt -r requirements-dev.txt
   pytest tests/ -v
   ```

2. **Start gateway (development):**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **View OpenAPI docs:**
   ```
   http://localhost:8000/docs      # Swagger UI
   http://localhost:8000/redoc     # ReDoc
   ```

4. **Test health endpoint:**
   ```bash
   curl http://localhost:8000/health/
   # Expected: {"status": "healthy", "timestamp": "..."}
   ```

5. **Test rate limiting:**
   ```bash
   # Send multiple requests rapidly
   for i in {1..110}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/devices/; done
   # Should get 429 after limit exceeded
   ```

6. **Test proxy (with backend unavailable):**
   ```bash
   curl http://localhost:8000/api/v1/devices/
   # Expected: {"detail": "Service unavailable"} with 503 status
   ```

7. **Test circuit breaker:**
   - Send requests to unavailable backend
   - After threshold failures, circuit opens
   - Subsequent requests get immediate 503 (circuit open)
   - Wait recovery timeout, circuit half-opens
   - Successful request closes circuit

---

## Notes

- **Framework:** FastAPI (async-native, lightweight, auto OpenAPI docs)
- **No database:** Gateway is stateless, uses Redis only for rate limiting cache
- **JWT validation:** Local validation using shared `JWT_SECRET_KEY` (no HTTP call to Auth Service)
- **Auth Service (Part 2):** Django-based, creates JWT tokens, user management, admin panel
- **Shared secret:** Both Gateway and Auth Service use same `JWT_SECRET_KEY` env variable
- **Routing:** Placeholder URLs for future microservices; update env vars as services are deployed
- **Async proxy:** Uses `httpx.AsyncClient` for high-performance proxying
- **No monolith dependency:** Fresh microservices architecture

## JWT Flow Summary

1. **Login:** User → Gateway → proxies to Auth Service → Auth creates JWT → returns to user
2. **API Request:** User (with JWT) → Gateway → validates JWT locally → injects X-User-ID → proxies to backend
3. **No Auth Service call** needed for validation (only for login/refresh/logout)
