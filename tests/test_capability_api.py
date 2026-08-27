"""Unit contracts for the standard Expert capability report endpoint."""
from fastapi.testclient import TestClient

from app.main import app


def test_capability_report_is_available_to_non_gradio_consumers(monkeypatch):
    """Other systems can consume the same report used by the Admin UI."""
    monkeypatch.setattr("app.api.runs.capability_report", lambda expert_id: {"expert_profile_id": expert_id, "capability_score": 80})
    response = TestClient(app).get("/api/v1/expert/profiles/housing_digitalization/capability-report")
    assert response.status_code == 200
    assert response.json()["capability_score"] == 80
