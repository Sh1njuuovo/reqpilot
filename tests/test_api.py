from fastapi.testclient import TestClient

import reqpilot.api as api_module
from reqpilot.api import app
from reqpilot.pipeline import SAMPLE_REQUIREMENT
from reqpilot.pipeline import run_pipeline as real_run_pipeline


def test_create_requirement_and_read_back(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "run_pipeline",
        lambda *a, **kw: real_run_pipeline(*a, **{**kw, "provider_name": "mock"}),
    )
    client = TestClient(app)
    resp = client.post("/requirements", json={"text": SAMPLE_REQUIREMENT})
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
