"""Staged pipeline API tests."""

from fastapi.testclient import TestClient

from eda_platform.api.main import app
from tests.test_logic_checker import _valid_project_state

client = TestClient(app)


def test_pipeline_run_success():
    body = {
        "project_state": _valid_project_state().model_dump(),
        "schematic_approved": True,
    }
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert any(s["stage"] == "firmware_generate" and s["success"] for s in data["stages"])


def test_pipeline_stops_without_schematic_approval():
    body = {
        "project_state": _valid_project_state().model_dump(),
        "schematic_approved": False,
    }
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    assert res.json()["success"] is False
