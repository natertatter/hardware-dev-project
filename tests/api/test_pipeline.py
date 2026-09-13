"""Staged pipeline API tests."""

from fastapi.testclient import TestClient

from eda_platform.api.main import app
from eda_platform.api.project_loader import save_operations_master, save_project_metadata
from eda_platform.schemas import (
    FidelityLevel,
    OperationStep,
    OperationsSequence,
    ProjectMetadata,
    TimingConstraint,
)
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


def test_pipeline_ignores_body_approval_without_override():
    save_project_metadata(
        ProjectMetadata(project_id="valid_i2c_wiring", schematic_approved=False)
    )
    body = {
        "project_state": _valid_project_state().model_dump(),
        "schematic_approved": True,
    }
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


def test_pipeline_loads_operations_master_from_disk():
    project_id = "valid_i2c_wiring"
    ops = OperationsSequence(
        project_id=project_id,
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="run2",
                description="Log bus current every second",
                hal_call="hal_sensor_read()",
                target_node_id="sensor_1",
                timing=TimingConstraint(period_ms=1000),
            ),
        ],
    )
    save_operations_master(ops)
    save_project_metadata(
        ProjectMetadata(
            project_id=project_id,
            schematic_approved=True,
            operations_approved=True,
        )
    )
    body = {"project_state": _valid_project_state().model_dump()}
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "runtime/ops_interpreter.c" in data["firmware_files_written"]


def test_pipeline_stops_when_operations_not_approved():
    project_id = "valid_i2c_wiring"
    ops = OperationsSequence(
        project_id=project_id,
        fidelity=FidelityLevel.TIMED,
        steps=[OperationStep(step_id="s1", description="Enable power rail")],
    )
    save_operations_master(ops)
    save_project_metadata(
        ProjectMetadata(
            project_id=project_id,
            schematic_approved=True,
            operations_approved=False,
        )
    )
    body = {"project_state": _valid_project_state().model_dump()}
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert any(s["stage"] == "operations_approve" and not s["success"] for s in data["stages"])


def test_pipeline_refine_stage_when_requested():
    project_id = "valid_i2c_wiring"
    ops = OperationsSequence(
        project_id=project_id,
        fidelity=FidelityLevel.NARRATIVE,
        narrative="poll the current sensor",
        steps=[],
    )
    save_project_metadata(
        ProjectMetadata(project_id=project_id, schematic_approved=True, operations_approved=True)
    )
    body = {
        "project_state": _valid_project_state().model_dump(),
        "operations": ops.model_dump(),
        "refine": True,
        "persist_refine": False,
        "allow_unapproved": True,
        "schematic_approved": True,
        "operations_approved": True,
    }
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 200
    stages = [s["stage"] for s in res.json()["stages"]]
    assert "operations_refine" in stages


def test_pipeline_missing_manifests_returns_422():
    body = {
        "project_state": _valid_project_state().model_dump(),
        "manifests": {},
        "allow_unapproved": True,
        "schematic_approved": True,
    }
    res = client.post("/api/v1/pipeline/run", json=body)
    assert res.status_code == 422
