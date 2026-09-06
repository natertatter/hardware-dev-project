"""Tests for firmware node classification."""

import pytest

from eda_platform.agents.firmware_engineer import FirmwareEngineerError, classify_nodes
from eda_platform.agents.firmware_engineer.models import ExecutionTier
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def test_ina219_classified_as_t1():
    project = _valid_project_state()
    classifications = classify_nodes(project, mock_manifests())
    sensor = next(c for c in classifications if c.node_id == "sensor_1")
    assert sensor.tier == ExecutionTier.T1
    assert sensor.hal_module == "hal_sensor_1"


def test_mcu_not_classified():
    project = _valid_project_state()
    classifications = classify_nodes(project, mock_manifests())
    assert all(c.node_id != "mcu_1" for c in classifications)


def test_no_peripherals_raises():
    from eda_platform.schemas import Node, ProjectState, Net, NetConnection, NetType

    project = ProjectState(
        project_id="mcu_only",
        nodes=[Node(node_id="mcu_1", component_id="mcu_rp2040")],
        nets=[
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
            )
        ],
    )
    with pytest.raises(FirmwareEngineerError, match="no schedulable peripheral"):
        classify_nodes(project, mock_manifests())
