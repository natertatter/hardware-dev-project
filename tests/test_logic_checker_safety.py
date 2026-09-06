"""Additional Logic Checker rule tests (Phase 5.1 safety rules)."""

import pytest

from eda_platform.agents.logic_checker import LogicCheckerError, validate_project
from eda_platform.schemas import Net, NetConnection, NetType, Node, Pin, PinType, ProjectState
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state

MANIFESTS = mock_manifests()


def test_missing_gnd_fails():
    project = ProjectState(
        project_id="no_gnd",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="sensor_1", component_id="sens_ina219"),
        ],
        nets=[
            Net(
                net_id="net_vcc",
                net_type=NetType.POWER,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="3V3_OUT"),
                    NetConnection(node_id="sensor_1", pin_id="VCC"),
                ],
            ),
        ],
    )
    with pytest.raises(LogicCheckerError, match="GND"):
        validate_project(project, MANIFESTS)


def test_current_budget_exceeded_fails():
    """Two high-draw sensors should exceed the 300mA 3V3_OUT limit."""
    manifests = dict(MANIFESTS)
    heavy = manifests["sens_ina219"].model_copy(
        update={
            "power_requirements": manifests["sens_ina219"].power_requirements.model_copy(
                update={"max_current_draw_ma": 200.0}
            )
        }
    )
    manifests["sens_heavy"] = heavy.model_copy(update={"component_id": "sens_heavy"})

    project = ProjectState(
        project_id="over_budget",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="sensor_1", component_id="sens_heavy"),
            Node(node_id="sensor_2", component_id="sens_heavy"),
        ],
        nets=[
            Net(
                net_id="net_vcc",
                net_type=NetType.POWER,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="3V3_OUT"),
                    NetConnection(node_id="sensor_1", pin_id="VCC"),
                    NetConnection(node_id="sensor_2", pin_id="VCC"),
                ],
            ),
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GND"),
                    NetConnection(node_id="sensor_1", pin_id="GND"),
                    NetConnection(node_id="sensor_2", pin_id="GND"),
                ],
            ),
        ],
    )
    with pytest.raises(LogicCheckerError, match="current budget"):
        validate_project(project, manifests)


def test_output_to_output_conflict_fails():
    project = ProjectState(
        project_id="out_conflict",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="mcu_2", component_id="mcu_rp2040"),
        ],
        nets=[
            Net(
                net_id="net_out",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO12"),
                    NetConnection(node_id="mcu_2", pin_id="GPIO12"),
                ],
            ),
        ],
    )
    with pytest.raises(LogicCheckerError, match="output-to-output"):
        validate_project(project, MANIFESTS)


def test_uart_tx_to_tx_fails():
    manifests = dict(MANIFESTS)
    uart_mcu = manifests["mcu_rp2040"].model_copy(
        update={
            "pins": [
                *manifests["mcu_rp2040"].pins,
                Pin(pin_id="UART0_TX", pin_type=PinType.UART_TX),
                Pin(pin_id="UART1_TX", pin_type=PinType.UART_TX),
            ]
        }
    )
    manifests["mcu_uart"] = uart_mcu.model_copy(update={"component_id": "mcu_uart"})

    project = ProjectState(
        project_id="uart_bad",
        nodes=[Node(node_id="mcu_1", component_id="mcu_uart")],
        nets=[
            Net(
                net_id="net_uart",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="UART0_TX"),
                    NetConnection(node_id="mcu_1", pin_id="UART1_TX"),
                ],
            ),
        ],
    )
    with pytest.raises(LogicCheckerError, match="UART polarity"):
        validate_project(project, manifests)


def test_valid_wiring_still_passes_with_new_rules():
    validate_project(_valid_project_state(), MANIFESTS)
