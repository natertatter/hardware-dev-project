"""Tests for ComponentManifest and ProjectState Pydantic schemas."""

import pytest
from pydantic import ValidationError

from eda_platform.schemas import (
    ActiveState,
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


def _sample_manifest() -> ComponentManifest:
    return ComponentManifest(
        component_id="mcu_rp2040",
        name="RP2040 Microcontroller",
        type=ComponentType.MCU,
        power_requirements=PowerRequirements(
            min_operating_voltage=1.8,
            max_operating_voltage=3.3,
            logic_level_voltage=3.3,
            max_current_draw_ma=500.0,
        ),
        pins=[
            Pin(
                pin_id="GPIO12",
                pin_type=PinType.GPIO_OUT,
                supported_features=["PWM", "ADC"],
                max_current_source_ma=12.0,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(pin_id="VCC", pin_type=PinType.POWER),
            Pin(pin_id="GND", pin_type=PinType.GND),
        ],
    )


def _sample_project_state() -> ProjectState:
    return ProjectState(
        project_id="demo_robot",
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
                    NetConnection(node_id="mcu_1", pin_id="VCC"),
                    NetConnection(node_id="sensor_1", pin_id="VCC"),
                ],
            ),
            Net(
                net_id="net_i2c_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GPIO12"),
                    NetConnection(node_id="sensor_1", pin_id="I2C_SDA"),
                ],
            ),
        ],
    )


class TestComponentManifest:
    def test_valid_manifest_round_trip(self):
        manifest = _sample_manifest()
        data = manifest.model_dump()
        restored = ComponentManifest.model_validate(data)
        assert restored.component_id == "mcu_rp2040"
        assert restored.pins[0].supported_features == ["PWM", "ADC"]

    def test_i2c_address_must_be_hex(self):
        with pytest.raises(ValidationError):
            ComponentManifest(
                component_id="sens_test",
                name="Test Sensor",
                type=ComponentType.SENSOR,
                power_requirements=PowerRequirements(
                    min_operating_voltage=3.0,
                    max_operating_voltage=3.6,
                    logic_level_voltage=3.3,
                    max_current_draw_ma=10.0,
                ),
                default_i2c_address="40",
                pins=[Pin(pin_id="VCC", pin_type=PinType.POWER)],
            )

    def test_max_voltage_must_be_gte_min(self):
        with pytest.raises(ValidationError):
            PowerRequirements(
                min_operating_voltage=5.0,
                max_operating_voltage=3.3,
                logic_level_voltage=3.3,
                max_current_draw_ma=100.0,
            )

    def test_component_id_pattern(self):
        with pytest.raises(ValidationError):
            ComponentManifest(
                component_id="Invalid-ID",
                name="Bad",
                type=ComponentType.PASSIVE,
                power_requirements=PowerRequirements(
                    min_operating_voltage=0.0,
                    max_operating_voltage=5.0,
                    logic_level_voltage=3.3,
                    max_current_draw_ma=0.0,
                ),
                pins=[Pin(pin_id="GND", pin_type=PinType.GND)],
            )


class TestProjectState:
    def test_valid_project_state_round_trip(self):
        state = _sample_project_state()
        data = state.model_dump()
        restored = ProjectState.model_validate(data)
        assert restored.project_id == "demo_robot"
        assert len(restored.nets) == 2

    def test_duplicate_node_ids_rejected(self):
        with pytest.raises(ValidationError):
            ProjectState(
                project_id="dup_test",
                nodes=[
                    Node(node_id="mcu_1", component_id="mcu_rp2040"),
                    Node(node_id="mcu_1", component_id="mcu_rp2040"),
                ],
                nets=[
                    Net(
                        net_id="net_gnd",
                        net_type=NetType.GND,
                        connections=[NetConnection(node_id="mcu_1", pin_id="GND")],
                    ),
                ],
            )

    def test_assigned_i2c_address_normalized(self):
        node = Node(
            node_id="sensor_1",
            component_id="sens_ina219",
            assigned_i2c_address="0x48",
        )
        assert node.assigned_i2c_address == "0x48"

    def test_invalid_i2c_address_on_node(self):
        with pytest.raises(ValidationError):
            Node(node_id="s1", component_id="sens_x", assigned_i2c_address="not_hex")
