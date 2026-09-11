"""Tests for multi-protocol template auto-wiring."""

from eda_platform.agents.architect.template_layout import template_auto_wire
from eda_platform.schemas import Net, NetConnection, NetType, Node, ProjectState
from tests.data.mock_data import mock_manifests


def _load_bme280_manifest():
    from pathlib import Path

    from eda_platform.schemas import ComponentManifest

    path = Path(__file__).resolve().parents[2] / "hardware_library" / "manifests" / "sens_bme280.example.json"
    return ComponentManifest.model_validate_json(path.read_text())


def test_spi_auto_wire_adds_spi_nets():
    manifests = mock_manifests()
    manifests["sens_bme280"] = _load_bme280_manifest()

    project = ProjectState(
        project_id="spi_test",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(
                node_id="sensor_1",
                component_id="sens_bme280",
                selected_protocol="SPI",
            ),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
            )
        ],
    )

    updated, wires_added = template_auto_wire(project, manifests)
    assert wires_added >= 6
    net_ids = {n.net_id for n in updated.nets}
    assert "auto_sensor_1_spi_mosi" in net_ids
    assert "auto_sensor_1_spi_miso" in net_ids
    assert "auto_sensor_1_spi_sck" in net_ids
    assert "auto_sensor_1_spi_cs" in net_ids
