FROM python:3.13-slim

WORKDIR /app

# Install git (needed for git+https:// dependencies)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api-gateway/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
