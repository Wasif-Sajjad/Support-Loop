"""Starter smoke test — expand per AGENTS.md (every non-trivial function needs a test)."""
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
