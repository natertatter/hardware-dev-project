"""Integration tests for the Logic Checker electrical validation engine.

Runnable via pytest or directly:

    python3 -m pytest tests/test_logic_checker.py -v
    python3 tests/test_logic_checker.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest

from eda_platform.agents.logic_checker import LogicCheckerError, validate_project
from eda_platform.schemas import Net, NetConnection, NetType, Node, ProjectState
from tests.data.mock_data import mock_manifests


def _valid_project_state() -> ProjectState:
    """MCU 3.3V OUT + GND + I2C connected to INA219 — should pass validation."""
    return ProjectState(
        project_id="valid_i2c_wiring",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(
                node_id="sensor_1",
                component_id="sens_ina219",
                assigned_i2c_address="0x40",
            ),
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
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GND"),
                    NetConnection(node_id="sensor_1", pin_id="GND"),
                ],
            ),
            Net(
                net_id="net_i2c_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                ],
            ),
            Net(
                net_id="net_i2c_scl",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO5"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SCL"),
                ],
            ),
        ],
    )


def _voltage_mismatch_project_state() -> ProjectState:
    """MCU 5V VBUS wired directly to sensor 3.3V VCC — should fail validation."""
    return ProjectState(
        project_id="voltage_mismatch",
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
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GND"),
                    NetConnection(node_id="sensor_1", pin_id="GND"),
                ],
            ),
        ],
    )


def _pin_collision_project_state() -> ProjectState:
    """MCU SDA pin on two separate non-bus nets — should fail validation."""
    return ProjectState(
        project_id="pin_collision",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(node_id="sensor_1", component_id="sens_ina219"),
        ],
        nets=[
            Net(
                net_id="net_sda_a",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                ],
            ),
            Net(
                net_id="net_sda_b",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                ],
            ),
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GND"),
                    NetConnection(node_id="sensor_1", pin_id="GND"),
                ],
            ),
        ],
    )


def _i2c_collision_project_state() -> ProjectState:
    """Two I2C sensors with the same address on one bus — should fail validation."""
    return ProjectState(
        project_id="i2c_collision",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(
                node_id="sensor_1",
                component_id="sens_ina219",
                assigned_i2c_address="0x40",
            ),
            Node(
                node_id="sensor_2",
                component_id="sens_ina219",
                assigned_i2c_address="0x40",
            ),
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
            Net(
                net_id="net_i2c_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                    NetConnection(node_id="sensor_2", pin_id="I2C_SDA"),
                ],
            ),
            Net(
                net_id="net_i2c_scl",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO5"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SCL"),
                    NetConnection(node_id="sensor_2", pin_id="I2C_SCL"),
                ],
            ),
        ],
    )


def _bus_pin_spans_two_buses_project_state() -> ProjectState:
    """MCU's SDA pin wired into two distinct I2C bus nets — should fail validation.

    Even though both nets are net_type=BUS, the same physical GPIO4 pin cannot
    belong to two separate bus nets without shorting them together.
    """
    return ProjectState(
        project_id="bus_pin_spans_two_buses",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(
                node_id="sensor_1",
                component_id="sens_ina219",
                assigned_i2c_address="0x40",
            ),
            Node(
                node_id="sensor_2",
                component_id="sens_ina219",
                assigned_i2c_address="0x41",
            ),
        ],
        nets=[
            Net(
                net_id="net_i2c_bus_0_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                ],
            ),
            Net(
                net_id="net_i2c_bus_1_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_2", pin_id="I2C_SDA"),
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


def _shared_bus_net_multiple_devices_project_state() -> ProjectState:
    """Three devices sharing ONE I2C bus net — must NOT be flagged as a collision.

    This is the legitimate "except I2C/SPI buses" case: many connections, one
    net_id, per bus line. Distinct from _bus_pin_spans_two_buses_project_state
    where the same pin spans two *different* net_ids.
    """
    return ProjectState(
        project_id="shared_bus_many_devices",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_rp2040"),
            Node(
                node_id="sensor_1",
                component_id="sens_ina219",
                assigned_i2c_address="0x40",
            ),
            Node(
                node_id="sensor_2",
                component_id="sens_ina219",
                assigned_i2c_address="0x41",
            ),
        ],
        nets=[
            Net(
                net_id="net_i2c_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO4"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                    NetConnection(node_id="sensor_2", pin_id="I2C_SDA"),
                ],
            ),
            Net(
                net_id="net_i2c_scl",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO5"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SCL"),
                    NetConnection(node_id="sensor_2", pin_id="I2C_SCL"),
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


MANIFESTS = mock_manifests()


class TestLogicChecker:
    def test_a_valid_wiring_passes(self):
        """Test A: Valid 3.3V + I2C wiring passes all checks."""
        validate_project(_valid_project_state(), MANIFESTS)

    def test_b_voltage_mismatch_fails(self):
        """Test B: 5V VBUS to 3.3V VCC raises a fatal voltage error."""
        with pytest.raises(LogicCheckerError, match="voltage mismatch"):
            validate_project(_voltage_mismatch_project_state(), MANIFESTS)

    def test_c_pin_collision_fails(self):
        """Test C: MCU SDA on two non-bus nets raises a pin collision error."""
        with pytest.raises(LogicCheckerError, match="pin collision"):
            validate_project(_pin_collision_project_state(), MANIFESTS)

    def test_d_i2c_address_collision_fails(self):
        """Test D: Duplicate I2C addresses on the same bus raise a collision error."""
        with pytest.raises(LogicCheckerError, match="I2C address collision"):
            validate_project(_i2c_collision_project_state(), MANIFESTS)

    def test_bus_pin_spanning_two_bus_nets_fails(self):
        """A pin cannot span two distinct bus nets, even though both are BUS type."""
        with pytest.raises(LogicCheckerError, match="pin collision"):
            validate_project(_bus_pin_spans_two_buses_project_state(), MANIFESTS)

    def test_shared_bus_net_multiple_devices_passes(self):
        """Multiple devices sharing one bus net (same net_id) is not a collision."""
        validate_project(_shared_bus_net_multiple_devices_project_state(), MANIFESTS)

    def test_unknown_component_id_raises(self):
        """Defensive: a node referencing a component_id missing from the manifest
        dict raises LogicCheckerError instead of a raw KeyError/AttributeError."""
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
        with pytest.raises(LogicCheckerError, match="unknown component_id"):
            validate_project(project, MANIFESTS)

    def test_unknown_pin_id_raises(self):
        """Defensive: a connection referencing a pin_id absent from the manifest
        raises LogicCheckerError rather than silently passing validation."""
        project = ProjectState(
            project_id="unknown_pin",
            nodes=[Node(node_id="mcu_1", component_id="mcu_rp2040")],
            nets=[
                Net(
                    net_id="net_bogus",
                    net_type=NetType.SIGNAL,
                    connections=[NetConnection(node_id="mcu_1", pin_id="GPIO99")],
                ),
            ],
        )
        with pytest.raises(LogicCheckerError, match="has no pin"):
            validate_project(project, MANIFESTS)


def main() -> int:
    """Run integration tests headlessly (no pytest required)."""
    tests = [
        ("Test A (Pass)", lambda: validate_project(_valid_project_state(), MANIFESTS)),
        (
            "Test B (Fail - Voltage)",
            lambda: _expect_logic_checker_error(
                lambda: validate_project(_voltage_mismatch_project_state(), MANIFESTS),
                "voltage mismatch",
            ),
        ),
        (
            "Test C (Fail - Pin Collision)",
            lambda: _expect_logic_checker_error(
                lambda: validate_project(_pin_collision_project_state(), MANIFESTS),
                "pin collision",
            ),
        ),
        (
            "Test D (Fail - I2C Collision)",
            lambda: _expect_logic_checker_error(
                lambda: validate_project(_i2c_collision_project_state(), MANIFESTS),
                "i2c address collision",
            ),
        ),
        (
            "Test E (Fail - Bus Pin Spans Two Buses)",
            lambda: _expect_logic_checker_error(
                lambda: validate_project(_bus_pin_spans_two_buses_project_state(), MANIFESTS),
                "pin collision",
            ),
        ),
        (
            "Test F (Pass - Shared Bus, Multiple Devices)",
            lambda: validate_project(_shared_bus_net_multiple_devices_project_state(), MANIFESTS),
        ),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
        except LogicCheckerError as exc:
            print(f"  FAIL  {name}: unexpected LogicCheckerError: {exc}")

    print(f"\n{passed}/{len(tests)} integration tests passed")
    return 0 if passed == len(tests) else 1


def _expect_logic_checker_error(fn, expected_substring: str) -> None:
    try:
        fn()
    except LogicCheckerError as exc:
        if expected_substring not in str(exc).lower():
            raise AssertionError(
                f"expected '{expected_substring}' in error message, got: {exc}"
            ) from exc
    else:
        raise AssertionError(f"expected LogicCheckerError containing '{expected_substring}'")


if __name__ == "__main__":
    sys.exit(main())
