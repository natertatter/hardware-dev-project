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


def test_rpi4_spi_auto_wire_adds_spi_nets():
    from pathlib import Path

    from eda_platform.schemas import ComponentManifest

    root = Path(__file__).resolve().parents[2] / "hardware_library" / "manifests"
    manifests = {
        "mcu_rpi4": ComponentManifest.model_validate_json(
            (root / "mcu_rpi4.example.json").read_text()
        ),
        "sens_bme280": _load_bme280_manifest(),
    }
    project = ProjectState(
        project_id="rpi4_spi",
        nodes=[
            Node(node_id="pi_1", component_id="mcu_rpi4"),
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
                connections=[NetConnection(node_id="pi_1", pin_id="GND")],
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
    mosi = next(n for n in updated.nets if n.net_id == "auto_sensor_1_spi_mosi")
    assert {c.pin_id for c in mosi.connections} == {"GPIO10_SPI_MOSI", "SDI"}


def test_auto_wire_is_idempotent_after_ui_renames_nets():
    """Canvas compile/decompile renames auto_* nets to net_vcc_0 / net_bus_0.

    A second Auto-Wire must not duplicate power/bus connections that already
    exist electrically, even when the net_id no longer matches the template.
    """
    manifests = mock_manifests()
    manifests["sens_bme280"] = _load_bme280_manifest()
    project = ProjectState(
        project_id="spi_roundtrip",
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
                net_id="net_vcc_0",
                net_type=NetType.POWER,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="3V3_OUT"),
                    NetConnection(node_id="sensor_1", pin_id="VCC"),
                ],
            ),
            Net(
                net_id="net_gnd_0",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GND"),
                    NetConnection(node_id="sensor_1", pin_id="GND"),
                ],
            ),
            Net(
                net_id="net_bus_0",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO18"),
                    NetConnection(node_id="sensor_1", pin_id="SDI"),
                ],
            ),
            Net(
                net_id="net_bus_1",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO19"),
                    NetConnection(node_id="sensor_1", pin_id="SDO"),
                ],
            ),
            Net(
                net_id="net_bus_2",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO20"),
                    NetConnection(node_id="sensor_1", pin_id="SCK"),
                ],
            ),
            Net(
                net_id="net_bus_3",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO17"),
                    NetConnection(node_id="sensor_1", pin_id="CSB"),
                ],
            ),
        ],
    )
    updated, wires_added = template_auto_wire(project, manifests)
    assert wires_added == 0
    assert len(updated.nets) == len(project.nets)


def test_spi_auto_wire_assigns_distinct_cs_pins():
    from pathlib import Path

    from eda_platform.schemas import ComponentManifest

    root = Path(__file__).resolve().parents[2] / "hardware_library" / "manifests"
    manifests = {
        "mcu_rpi4": ComponentManifest.model_validate_json(
            (root / "mcu_rpi4.example.json").read_text()
        ),
        "sens_bme280": _load_bme280_manifest(),
    }
    project = ProjectState(
        project_id="two_spi",
        nodes=[
            Node(node_id="pi_1", component_id="mcu_rpi4"),
            Node(
                node_id="sensor_1",
                component_id="sens_bme280",
                selected_protocol="SPI",
            ),
            Node(
                node_id="sensor_2",
                component_id="sens_bme280",
                selected_protocol="SPI",
            ),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="pi_1", pin_id="GND")],
            )
        ],
    )
    updated, _wires = template_auto_wire(project, manifests)
    cs_nets = [n for n in updated.nets if n.net_id.endswith("_spi_cs")]
    assert len(cs_nets) == 2
    mcu_cs = {
        c.pin_id
        for n in cs_nets
        for c in n.connections
        if c.node_id == "pi_1"
    }
    assert mcu_cs == {"GPIO8_SPI_CE0", "GPIO7_SPI_CE1"}
