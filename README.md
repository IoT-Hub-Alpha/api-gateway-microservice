# API Gateway Microservice

Central entry point for all backend microservices. Handles routing, proxying, and circuit breaking.

## Features

- Proxy requests to backend services
- Circuit breaker (prevents cascading failures)
- Structured JSON logging
- Health check endpoints

## Quick Start

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env file
cp .env.example .env

# Run
uvicorn app.main:app --reload --port 8000 --no-access-log
```

### Docker

```bash
# Build
docker build -t api-gateway .

# Run
docker run -p 8000:8000 --env-file .env api-gateway
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check |
| `/ready` | GET | Readiness check |
| `/{service}/{path}` | ANY | Proxy to backend service |

### Proxy Examples

```bash
# Proxies to DEVICES_SERVICE_URL/posts/1
curl http://localhost:8000/devices/posts/1

# Proxies to AUTH_SERVICE_URL/login
curl -X POST http://localhost:8000/auth/login
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (development/production) | `development` |
| `APP_NAME` | Application name | `api-gateway` |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `AUTH_SERVICE_URL` | Auth service URL | `http://auth-service:8005` |
| `DEVICES_SERVICE_URL` | Devices service URL | `http://devices-service:8001` |
| `TELEMETRY_SERVICE_URL` | Telemetry service URL | `http://telemetry-service:8002` |
| `RULES_SERVICE_URL` | Rules service URL | `http://rules-service:8003` |
| `EVENTS_SERVICE_URL` | Events service URL | `http://events-service:8004` |
| `DEFAULT_TIMEOUT` | Request timeout (seconds) | `30` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before circuit opens | `5` |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | Seconds before retry | `30` |

## Project Structure

```
app/
├── main.py              # FastAPI application
├── api/
│   └── router.py        # API routes
├── core/
│   └── config.py        # Configuration
└── services/
    ├── proxy.py         # Proxy logic
    └── circuit_breaker.py
```

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Format code
black app/

# Lint
flake8 app/

# Run tests
pytest
```

## Circuit Breaker

Protects against cascading failures:

- **CLOSED**: Normal operation
- **OPEN**: Requests rejected immediately (503)
- **HALF_OPEN**: Testing if service recovered

After `CIRCUIT_BREAKER_FAILURE_THRESHOLD` failures, circuit opens. After `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` seconds, it tries one request.
