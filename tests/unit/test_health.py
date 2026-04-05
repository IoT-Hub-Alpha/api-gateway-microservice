class TestHealthEndpoints:
    def test_health_returns_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_ready_returns_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
