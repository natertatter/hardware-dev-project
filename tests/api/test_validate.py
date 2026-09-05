"""API integration tests for validation, manifests, and auto-wire."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from eda_platform.api.main import app
from eda_platform.schemas import Net, NetConnection, NetType, Node, ProjectState
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state

client = TestClient(app)
MANIFESTS = mock_manifests()


def _valid_payload() -> dict:
    return {"project_state": _valid_project_state().model_dump()}


class TestHealth:
    def test_health_ok(self):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


class TestManifestsAPI:
    def test_list_manifests(self):
        res = client.get("/api/v1/manifests")
        assert res.status_code == 200
        data = res.json()
        assert "manifests" in data
        ids = {m["component_id"] for m in data["manifests"]}
        assert "mcu_rp2040" in ids
        assert "sens_ina219" in ids

    def test_get_manifest_by_id(self):
        res = client.get("/api/v1/manifests/mcu_rp2040")
        assert res.status_code == 200
        assert res.json()["component_id"] == "mcu_rp2040"

    def test_get_manifest_not_found(self):
        res = client.get("/api/v1/manifests/does_not_exist")
        assert res.status_code == 404


class TestValidateAPI:
    def test_valid_project_passes(self):
        res = client.post("/api/v1/validate", json=_valid_payload())
        assert res.status_code == 200
        body = res.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_voltage_mismatch_returns_structured_errors(self):
        payload = _valid_payload()
        payload["project_state"]["nets"][0]["connections"][0]["pin_id"] = "VBUS"
        res = client.post("/api/v1/validate", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["valid"] is False
        assert any(e["rule"] == "check_voltage_levels" for e in body["errors"])

    def test_collects_multiple_rule_failures(self):
        """Missing GND and voltage mismatch should both appear in errors."""
        project = ProjectState(
            project_id="multi_fail",
            nodes=[
                Node(node_id="mcu_1", component_id="mcu_rp2040"),
                Node(node_id="sensor_1", component_id="sens_ina219"),
            ],
            nets=[
                Net(
                    net_id="net_vcc_bad",
                    net_type=NetType.POWER,
                    connections=[
                        NetConnection(node_id="mcu_1", pin_id="VBUS"),
                        NetConnection(node_id="sensor_1", pin_id="VCC"),
                    ],
                ),
            ],
        )
        res = client.post(
            "/api/v1/validate",
            json={"project_state": project.model_dump(), "manifests": {
                k: v.model_dump() for k, v in MANIFESTS.items()
            }},
        )
        body = res.json()
        assert body["valid"] is False
        rules = {e["rule"] for e in body["errors"]}
        assert "check_voltage_levels" in rules
        assert "check_common_gnd" in rules


class TestArchitectAPI:
    def test_auto_wire_placement_only(self):
        res = client.post(
            "/api/v1/architect/auto-wire",
            json={
                "project_state": {
                    "project_id": "auto_test",
                    "nodes": [
                        {"node_id": "mcu_1", "component_id": "mcu_rp2040"},
                        {"node_id": "sensor_1", "component_id": "sens_ina219"},
                    ],
                    "nets": [],
                }
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["wires_added"] == 4
        net_ids = {n["net_id"] for n in body["project_state"]["nets"]}
        assert "auto_sensor_1_vcc" in net_ids
        assert "auto_sensor_1_gnd" in net_ids

    def test_auto_wire_without_mcu_fails(self):
        res = client.post(
            "/api/v1/architect/auto-wire",
            json={
                "project_state": {
                    "project_id": "no_mcu",
                    "nodes": [
                        {"node_id": "sensor_1", "component_id": "sens_ina219"},
                    ],
                    "nets": [],
                }
            },
        )
        assert res.status_code == 400
