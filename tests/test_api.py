from fastapi.testclient import TestClient

from reqpilot.api import app
from reqpilot.pipeline import SAMPLE_REQUIREMENT


def test_create_requirement_and_read_back():
    client = TestClient(app)
    resp = client.post("/requirements", json={"text": SAMPLE_REQUIREMENT, "provider": "mock"})
    assert resp.status_code == 201
    data = resp.json()
    run_id = data["run_id"]
    assert data["status"] == "succeeded"

    assert client.get(f"/requirements/{run_id}").status_code == 200
    assert client.get(f"/requirements/{run_id}/prd").status_code == 200
    assert client.get(f"/requirements/{run_id}/issues").status_code == 200
    assert client.get(f"/requirements/{run_id}/tasks").status_code == 200
    proto = client.get(f"/requirements/{run_id}/prototype")
    assert proto.status_code == 200
    assert "<!doctype html>" in proto.text.lower()
    assert client.get(f"/requirements/{run_id}/tasks.csv").status_code == 200
    assert client.get(f"/requirements/{run_id}/prd.md").status_code == 200


def test_missing_run_returns_404():
    client = TestClient(app)
    assert client.get("/requirements/nope").status_code == 404


def test_health():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
