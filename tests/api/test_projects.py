"""Project persistence API tests."""

import pytest
from fastapi.testclient import TestClient

from eda_platform.api.main import app
from eda_platform.api.project_loader import (
    load_schematic_draft,
    project_directory,
    save_project_metadata,
    validate_project_id,
)
from eda_platform.schemas import ProjectMetadata

client = TestClient(app)


def test_list_projects_includes_demo_robot():
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert "demo_robot" in res.json()["project_ids"]


def test_put_and_get_schematic():
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


def test_placement_only_draft_save_has_empty_nets_on_disk():
    body = {
        "project_id": "placement_only",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [],
    }
    put = client.put("/api/v1/projects/placement_only/schematic", json=body)
    assert put.status_code == 200
    assert put.json()["schematic"]["nets"] == []

    on_disk = load_schematic_draft("placement_only")
    assert on_disk is not None
    assert on_disk.nets == []
    assert not any(n.net_id.startswith("_draft_") for n in on_disk.nets)


def test_project_directory_rejects_traversal():
    with pytest.raises(ValueError):
        project_directory("..")


def test_invalid_project_ids_rejected():
    for bad_id in ["..", "a/b", "../x", "", "a" * 65, "9starts_with_digit"]:
        with pytest.raises(ValueError):
            validate_project_id(bad_id)

    res = client.get(f"/api/v1/projects/{'a' * 65}/schematic")
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid project_id"


def test_metadata_round_trip():
    draft = {
        "project_id": "meta_test",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [],
    }
    client.put("/api/v1/projects/meta_test/schematic", json=draft)

    get_meta = client.get("/api/v1/projects/meta_test/metadata")
    assert get_meta.status_code == 200
    assert get_meta.json()["metadata"]["project_id"] == "meta_test"

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


def test_schematic_change_clears_both_approvals():
    wired = {
        "project_id": "approval_reset",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [
            {
                "net_id": "net_gnd",
                "net_type": "GND",
                "connections": [
                    {"node_id": "mcu_1", "pin_id": "GND"},
                    {"node_id": "mcu_1", "pin_id": "GND"},
                ],
            }
        ],
    }
    client.put("/api/v1/projects/approval_reset/schematic", json=wired)
    save_project_metadata(
        ProjectMetadata(
            project_id="approval_reset",
            schematic_approved=True,
            operations_approved=True,
            operations_fidelity="narrative",
        )
    )

    wired["nodes"].append({"node_id": "sensor_1", "component_id": "sens_ina219"})
    client.put("/api/v1/projects/approval_reset/schematic", json=wired)

    meta = client.get("/api/v1/projects/approval_reset/metadata").json()["metadata"]
    assert meta["schematic_approved"] is False
    assert meta["operations_approved"] is False


def test_identical_schematic_save_preserves_approvals():
    body = {
        "project_id": "noop_save",
        "nodes": [{"node_id": "mcu_1", "component_id": "mcu_rp2040"}],
        "nets": [
            {
                "net_id": "net_gnd",
                "net_type": "GND",
                "connections": [
                    {"node_id": "mcu_1", "pin_id": "GND"},
                    {"node_id": "mcu_1", "pin_id": "GND"},
                ],
            }
        ],
    }
    client.put("/api/v1/projects/noop_save/schematic", json=body)
    save_project_metadata(
        ProjectMetadata(
            project_id="noop_save",
            schematic_approved=True,
            operations_approved=True,
            operations_fidelity="narrative",
        )
    )
    client.put("/api/v1/projects/noop_save/schematic", json=body)
    meta = client.get("/api/v1/projects/noop_save/metadata").json()["metadata"]
    assert meta["schematic_approved"] is True
    assert meta["operations_approved"] is True
