"""Staged pipeline API tests."""

from fastapi.testclient import TestClient

from eda_platform.api.main import app
from eda_platform.api.project_loader import save_project_metadata
from eda_platform.schemas import ProjectMetadata
from tests.test_logic_checker import _valid_project_state

client = TestClient(app)


def test_pipeline_run_success_uses_metadata_approval():
    project_id = "valid_i2c_wiring"
    save_project_metadata(
        ProjectMetadata(project_id=project_id, schematic_approved=True, operations_approved=False)
    )
    body = {"project_state": _valid_project_state().model_dump()}
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert any(s["stage"] == "firmware_generate" and s["success"] for s in data["stages"])


def test_pipeline_stops_without_schematic_approval_in_metadata():
    save_project_metadata(
        ProjectMetadata(project_id="valid_i2c_wiring", schematic_approved=False)
    )
    body = {"project_state": _valid_project_state().model_dump()}
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    assert res.json()["success"] is False


def test_pipeline_allow_unapproved_override():
    save_project_metadata(
        ProjectMetadata(project_id="valid_i2c_wiring", schematic_approved=False)
    )
    body = {
        "project_state": _valid_project_state().model_dump(),
        "allow_unapproved": True,
        "schematic_approved": True,
    }
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    assert res.json()["success"] is True
