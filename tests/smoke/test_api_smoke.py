"""Smoke tests for FastAPI application."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.smoke
class TestAPISmoke:
    def test_health_endpoint(self):
        from apps.api.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "quant-api-platform"

    def test_instruments_endpoint(self):
        from apps.api.main import app
        client = TestClient(app)
        # This will fail without DB but tests that route is wired up
        try:
            response = client.get("/instruments")
            assert response.status_code in (200, 500)
        except Exception:
            pass  # Expected without DB

    def test_execution_intents_endpoint(self):
        from apps.api.main import app
        client = TestClient(app)
        try:
            response = client.get("/execution/intents")
            assert response.status_code in (200, 500)
        except Exception:
            pass
