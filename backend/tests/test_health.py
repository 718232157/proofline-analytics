from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_service_identity() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Proofline Analytics API",
        "version": "0.1.0",
        "environment": "development",
        "assistant_mode": "deterministic",
        "llm_model": None,
        "numeric_source": "governed_analytics_api",
    }
