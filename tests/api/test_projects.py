"""Project persistence API tests."""

import pytest
from fastapi.testclient import TestClient

from eda_platform.api.main import app

client = TestClient(app)


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    import eda_platform.api.project_loader as pl

    monkeypatch.setattr(pl, "_PROJECTS_DIR", tmp_path / "projects")
    return tmp_path / "projects"


def test_list_projects_empty(tmp_project):
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert res.json()["project_ids"] == []


def test_put_and_get_schematic(tmp_project):
    body = {
        "project_id": "ui_save_test",
        "nodes": [
            {"node_id": "mcu_1", "component_id": "mcu_rp2040"},
            {"node_id": "sensor_1", "component_id": "sens_ina219", "assigned_i2c_address": "0x40"},
        ],
        "nets": [
            {
                "net_id": "net_gnd",
                "net_type": "GND",
                "connections": [
                    {"node_id": "mcu_1", "pin_id": "GND"},
                    {"node_id": "sensor_1", "pin_id": "GND"},
                ],
            }
        ],
    }
    put = client.put("/api/v1/projects/ui_save_test/schematic", json=body)
    assert put.status_code == 200
    assert put.json()["schematic"]["project_id"] == "ui_save_test"

    listed = client.get("/api/v1/projects")
    assert "ui_save_test" in listed.json()["project_ids"]

    get_res = client.get("/api/v1/projects/ui_save_test/schematic")
    assert get_res.status_code == 200
    assert get_res.json()["schematic"]["nodes"][0]["node_id"] == "mcu_1"


def test_placement_only_draft_save(tmp_project):
    body = {
        "project_id": "placement_only",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [],
    }
    put = client.put("/api/v1/projects/placement_only/schematic", json=body)
    assert put.status_code == 200
    schematic = put.json()["schematic"]
    assert schematic["project_id"] == "placement_only"
    assert len(schematic["nets"]) >= 1


def test_metadata_round_trip(tmp_project):
    draft = {
        "project_id": "meta_test",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [],
    }
    client.put("/api/v1/projects/meta_test/schematic", json=draft)

    get_meta = client.get("/api/v1/projects/meta_test/metadata")
    assert get_meta.status_code == 200
    assert get_meta.json()["metadata"]["project_id"] == "meta_test"
    assert get_meta.json()["metadata"]["schematic_approved"] is False

    updated = {
        "metadata": {
            "project_id": "meta_test",
            "schematic_approved": True,
            "operations_approved": False,
            "operations_fidelity": "narrative",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    }
    put_meta = client.put("/api/v1/projects/meta_test/metadata", json=updated)
    assert put_meta.status_code == 200
    assert put_meta.json()["metadata"]["schematic_approved"] is True
