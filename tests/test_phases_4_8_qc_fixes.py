"""Regression tests for the Phases 4–8 QC fix list."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eda_platform.agents.architect.template_layout import template_i2c_layout
from eda_platform.agents.logic_checker import validate_project_collect
from eda_platform.agents.logic_checker.logic_checker import LogicCheckerError, validate_project
from eda_platform.api.main import app
from eda_platform.api.manifest_loader import clear_manifest_cache, load_all_manifests
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    Net,
    NetConnection,
    NetType,
    Node,
    Pin,
    PinType,
    PowerRequirements,
    ProjectState,
)
from tests.data.mock_data import mock_manifests

client = TestClient(app)
MANIFESTS = mock_manifests()
MANIFESTS_DIR = Path(__file__).resolve().parents[1] / ".." / "hardware_library" / "manifests"


class TestManifestLoaderResilience:
    def test_invalid_manifest_file_does_not_crash_catalog(self, tmp_path, monkeypatch):
        from eda_platform.api import manifest_loader

        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        (manifests_dir / "good.json").write_text(
            mock_manifests()["mcu_rp2040"].model_dump_json()
        )
        (manifests_dir / "bad.json").write_text("{not valid json")

        monkeypatch.setattr(manifest_loader, "_MANIFESTS_DIR", manifests_dir)
        clear_manifest_cache()

        catalog = load_all_manifests()
        assert "mcu_rp2040" in catalog
        assert len(catalog) == 1

        res = client.get("/api/v1/manifests")
        assert res.status_code == 200
        assert len(res.json()["manifests"]) == 1

        clear_manifest_cache()


class TestTemplateLayoutPinTypeResolution:
    def test_sensor_with_vdd_instead_of_vcc_still_wires_power(self):
        sensor = ComponentManifest(
            component_id="sens_vdd",
            name="Sensor with VDD pin",
            type=ComponentType.SENSOR,
            power_requirements=PowerRequirements(
                min_operating_voltage=3.0,
                max_operating_voltage=3.6,
                logic_level_voltage=3.3,
                max_current_draw_ma=1.0,
            ),
            default_i2c_address="0x48",
            pins=[
                Pin(pin_id="VDD", pin_type=PinType.POWER),
                Pin(pin_id="VSS", pin_type=PinType.GND),
                Pin(pin_id="SDA", pin_type=PinType.I2C_SDA),
                Pin(pin_id="SCL", pin_type=PinType.I2C_SCL),
            ],
        )
        manifests = {**mock_manifests(), sensor.component_id: sensor}
        project = ProjectState(
            project_id="vdd_sensor",
            nodes=[
                Node(node_id="mcu_1", component_id="mcu_rp2040"),
                Node(node_id="sensor_1", component_id="sens_vdd"),
            ],
            nets=[
                Net(
                    net_id="placeholder",
                    net_type=NetType.GND,
                    connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
                )
            ],
        )

        updated, wires_added = template_i2c_layout(project, manifests)
        assert wires_added == 4
        vcc = next(n for n in updated.nets if n.net_id == "auto_sensor_1_vcc")
        assert ("sensor_1", "VDD") in {(c.node_id, c.pin_id) for c in vcc.connections}

    def test_unknown_component_id_raises_clear_error(self):
        project = ProjectState(
            project_id="unknown",
            nodes=[Node(node_id="n1", component_id="does_not_exist")],
            nets=[
                Net(
                    net_id="placeholder",
                    net_type=NetType.GND,
                    connections=[NetConnection(node_id="n1", pin_id="GND")],
                )
            ],
        )
        with pytest.raises(ValueError, match="unknown component_id"):
            template_i2c_layout(project, mock_manifests())


class TestStructuralValidation:
    def test_unknown_component_returns_single_structural_error(self):
        project = ProjectState(
            project_id="unknown_component",
            nodes=[Node(node_id="mystery_1", component_id="does_not_exist")],
            nets=[
                Net(
                    net_id="net_gnd",
                    net_type=NetType.GND,
                    connections=[NetConnection(node_id="mystery_1", pin_id="GND")],
                ),
            ],
        )
        result = validate_project_collect(project, MANIFESTS)
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].rule == "structural_integrity"


class TestUartPolarity:
    def test_two_tx_and_one_rx_on_same_net_fails(self):
        manifests = dict(MANIFESTS)
        uart_mcu = manifests["mcu_rp2040"].model_copy(
            update={
                "pins": [
                    *manifests["mcu_rp2040"].pins,
                    Pin(pin_id="UART0_TX", pin_type=PinType.UART_TX),
                    Pin(pin_id="UART1_TX", pin_type=PinType.UART_TX),
                    Pin(pin_id="UART0_RX", pin_type=PinType.UART_RX),
                ]
            }
        )
        manifests["mcu_uart"] = uart_mcu.model_copy(update={"component_id": "mcu_uart"})

        project = ProjectState(
            project_id="uart_mixed_conflict",
            nodes=[Node(node_id="mcu_1", component_id="mcu_uart")],
            nets=[
                Net(
                    net_id="net_uart",
                    net_type=NetType.SIGNAL,
                    connections=[
                        NetConnection(node_id="mcu_1", pin_id="UART0_TX"),
                        NetConnection(node_id="mcu_1", pin_id="UART1_TX"),
                        NetConnection(node_id="mcu_1", pin_id="UART0_RX"),
                    ],
                ),
            ],
        )
        with pytest.raises(LogicCheckerError, match="multiple TX"):
            validate_project(project, manifests)


class TestArchitectAPIErrors:
    def test_unknown_component_id_returns_clear_error(self):
        res = client.post(
            "/api/v1/architect/auto-wire",
            json={
                "project_state": {
                    "project_id": "unknown",
                    "nodes": [{"node_id": "n1", "component_id": "does_not_exist"}],
                    "nets": [],
                }
            },
        )
        assert res.status_code == 400
        assert "unknown component_id" in res.json()["detail"]
