"""API integration tests for operations sequence endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from eda_platform.api.main import app
from tests.test_logic_checker import _valid_project_state

client = TestClient(app)


def _narrative_payload() -> dict:
    return {
        "operations": {
            "project_id": "valid_i2c_wiring",
            "fidelity": "narrative",
            "version": 1,
            "narrative": "Enable power.\nPoll sensor_1 current.",
            "steps": [],
            "open_questions": [],
        },
        "project_state": _valid_project_state().model_dump(),
        "persist": False,
    }


class TestOperationsAPI:
    def test_refine_narrative(self):
        res = client.post("/api/v1/operations/refine", json=_narrative_payload())
        assert res.status_code == 200
        body = res.json()
        assert body["fidelity_promoted"] is True
        assert len(body["refined"]["steps"]) >= 2
        assert body["steps_bound"] >= 1

    def test_validate_refined_sequence(self):
        refine_res = client.post("/api/v1/operations/refine", json=_narrative_payload())
        refined = refine_res.json()["refined"]
        res = client.post(
            "/api/v1/operations/validate",
            json={
                "operations": refined,
                "project_state": _valid_project_state().model_dump(),
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["valid"] is True

    def test_get_demo_robot_master(self):
        res = client.get("/api/v1/projects/demo_robot/operations/master")
        assert res.status_code == 200
        assert res.json()["project_id"] == "demo_robot"
        assert res.json()["fidelity"] == "narrative"

    def test_save_and_load_master(self):
        seq = {
            "project_id": "api_test_ops",
            "fidelity": "steps",
            "version": 1,
            "steps": [
                {"step_id": "s1", "description": "Test step"},
            ],
            "open_questions": [],
        }
        put_res = client.put("/api/v1/projects/api_test_ops/operations/master", json=seq)
        assert put_res.status_code == 200
        get_res = client.get("/api/v1/projects/api_test_ops/operations/master")
        assert get_res.status_code == 200
        assert get_res.json()["steps"][0]["step_id"] == "s1"

    def test_merge_demo_robot(self):
        import json
        from pathlib import Path

        schematic = json.loads(
            Path("projects/demo_robot/schematic.json").read_text()
        )
        project_id = "demo_robot_merge_test"
        refine_res = client.post(
            "/api/v1/operations/refine",
            json={
                "operations": {
                    "project_id": project_id,
                    "fidelity": "narrative",
                    "version": 1,
                    "narrative": "Enable power.\nPoll sensor_1 current.",
                    "steps": [],
                    "open_questions": [],
                },
                "project_state": schematic | {"project_id": project_id},
                "persist": False,
            },
        )
        assert refine_res.status_code == 200
        refined = refine_res.json()["refined"]

        # Save schematic so merge endpoint can load it from disk
        from eda_platform.api.project_loader import save_project_state
        from eda_platform.schemas import ProjectState

        save_project_state(ProjectState.model_validate(schematic | {"project_id": project_id}))

        merge_res = client.post(
            "/api/v1/operations/merge",
            json={"operations": refined, "bump_version": True},
        )
        assert merge_res.status_code == 200
        assert merge_res.json()["master"]["version"] >= 1
