# API Gateway - Implementation Summary

## What We Built

FastAPI-based API Gateway that proxies requests to backend microservices.

## Completed Features

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI project structure | Done | `app/` with config, services, api |
| Health endpoints | Done | `/health`, `/ready` |
| Proxy to backend services | Done | `/{service}/{path}` routes to backend |
| Rate Limiting | Done | Redis-backed, per IP |
| Circuit Breaker | Done | Redis-backed, protects against cascading failures |
| Structured JSON logging | Done | Using `iot-logging` library |
| Dockerfile | Done | Python 3.13-slim, uvicorn |
| Configuration | Done | Pydantic settings + dotenv |
| Unit Tests | Done | pytest with 25 tests |

## Project Structure

```
api-gateway-microservice/
├── app/
│   ├── main.py                 # FastAPI app entry
│   ├── api/
│   │   └── router.py           # Routes: /health, /ready, proxy
│   ├── core/
│   │   └── config.py           # Settings (env vars)
│   └── services/
│       ├── proxy.py            # HTTP forwarding (httpx)
│       ├── circuit_breaker.py  # Circuit breaker (Redis)
│       └── rate_limiter.py     # Rate limiting (Redis)
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   └── unit/
│       ├── test_health.py
│       ├── test_proxy.py
│       ├── test_rate_limiter.py
│       └── test_circuit_breaker.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .env.example
├── .flake8
├── pyproject.toml
└── README.md
```

## Key Files

### requirements.txt
```
fastapi==0.111.0
uvicorn[standard]==0.30.1
python-dotenv==1.0.1
pydantic-settings==2.3.0
httpx==0.27.0
redis==5.0.8
iot-logging-schemas @ git+https://github.com/IoT-Hub-Alpha/logging-lib.git@dev
```

### Key Decisions Made

1. **No API versioning** (`/api/v1/`) - gateway just proxies, backends handle versioning
2. **No CORS** - undecided, will add if frontend needs it
3. **Redis for Rate Limiting & Circuit Breaker** - shared state across gateway instances
4. **iot-logging library** - shared structured logging across services
5. **Simple Config class** - single class using `os.getenv()` with defaults

## How It Works

```
Request Flow:
─────────────
Client → GET /devices/123
       → router.py (matches /{service}/{path})
       → proxy.py (checks rate limit, then circuit breaker)
       → rate_limiter.py (under limit? proceed)
       → circuit_breaker.py (CLOSED? proceed)
       → httpx forwards to DEVICES_SERVICE_URL/123
       → Response returned to client

Rate Limiting:
──────────────
Request → Get client IP → Check Redis counter → Allow or 429
- Default: 100 requests per 60 seconds
- Configurable via RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW

Circuit Breaker:
────────────────
CLOSED (normal) → 5 failures → OPEN (blocking)
                               ↓ 30 seconds
                            HALF_OPEN (test one request)
                               ↓ success
                            CLOSED
```

## Commands

```bash
# Local development
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 --no-access-log

# Docker (with Redis on host)
docker build -t api-gateway .
docker run -p 8000:8000 --env-file .env --add-host=host.docker.internal:host-gateway api-gateway

# Code quality
black app/
flake8 app/

# Tests
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Not Implemented (Future)

| Feature | Notes |
|---------|-------|
| JWT Authentication | Separate task, needs Auth Service |
| CORS | Add when frontend is ready |
| Rate limiting by user_id | Add after JWT is implemented |

## Related Services

- **Redis Service** - `Redis-Service/` for rate limiting and circuit breaker state
- **Auth Service** (Part 2) - Django, creates JWT tokens, user management
- **logging-lib** - Shared logging library (`iot-logging-schemas`)

## Environment Variables

See `.env.example` for full list. Key ones:

```env
# Backend Services
DEVICES_SERVICE_URL=http://devices-service:8001
AUTH_SERVICE_URL=http://auth-service:8005

# Redis
REDIS_URL=redis://redis-service:6379/0
REDIS_PASSWORD=redis123

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30
```

## Testing the Proxy

Without real services, use public API:

```env
DEVICES_SERVICE_URL=https://jsonplaceholder.typicode.com
```

```bash
# Test proxy
curl http://localhost:8000/devices/posts/1

# Test rate limiting (should get 429 after limit)
for i in {1..105}; do curl -s -o /dev/null -w "$i: %{http_code}\n" http://localhost:8000/devices/posts/1; done

# Check Redis state
docker exec redis-dev redis-cli -a redis123 KEYS "*"
```
