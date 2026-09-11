"""Tests for deterministic template I2C auto-wiring."""

from eda_platform.agents.architect.template_layout import template_i2c_layout
from eda_platform.schemas import Node, ProjectState
from tests.data.mock_data import mock_manifests


def test_template_i2c_layout_adds_four_nets():
    from eda_platform.schemas import Net, NetConnection, NetType

    project = ProjectState(
        project_id="layout_test",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="sensor_1", component_id="sens_ina219", assigned_i2c_address="0x40"),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
            )
        ],
    )

    updated, wires_added = template_i2c_layout(project, mock_manifests())

    assert wires_added == 4
    net_ids = {n.net_id for n in updated.nets}
    assert "auto_sensor_1_vcc" in net_ids
    assert "auto_sensor_1_gnd" in net_ids
    assert "auto_sensor_1_i2c_sda" in net_ids
    assert "auto_sensor_1_i2c_scl" in net_ids

    vcc = next(n for n in updated.nets if n.net_id == "auto_sensor_1_vcc")
    pins = {(c.node_id, c.pin_id) for c in vcc.connections}
    assert ("mcu_1", "3V3_OUT") in pins
    assert ("sensor_1", "VCC") in pins


def test_template_i2c_layout_is_idempotent():
    from eda_platform.schemas import Net, NetConnection, NetType

    project = ProjectState(
        project_id="idempotent",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="sensor_1", component_id="sens_ina219"),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
            )
        ],
    )
    manifests = mock_manifests()
    first, added_first = template_i2c_layout(project, manifests)
    assert added_first == 4

    second, added_second = template_i2c_layout(first, manifests)
    assert added_second == 0
    assert len(second.nets) == len(first.nets)
