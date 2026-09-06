"""Mock ComponentManifest fixtures for Logic Checker integration tests."""

from eda_platform.schemas import (
    ActiveState,
    ComponentManifest,
    ComponentType,
    Pin,
    PinType,
    PowerRequirements,
)


def mcu_rp2040_manifest() -> ComponentManifest:
    """Raspberry Pi Pico (RP2040) — 3.3 V logic, 5 V VBUS input, I2C on GPIO4/5."""
    return ComponentManifest(
        component_id="mcu_rp2040",
        name="Raspberry Pi Pico (RP2040)",
        type=ComponentType.MCU,
        power_requirements=PowerRequirements(
            min_operating_voltage=1.8,
            max_operating_voltage=5.5,
            logic_level_voltage=3.3,
            max_current_draw_ma=500.0,
        ),
        pins=[
            Pin(
                pin_id="VBUS",
                pin_type=PinType.POWER,
                supported_features=[],
                max_current_source_ma=None,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(
                pin_id="3V3_OUT",
                pin_type=PinType.POWER,
                supported_features=[],
                max_current_source_ma=300.0,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(
                pin_id="GND",
                pin_type=PinType.GND,
            ),
            Pin(
                pin_id="GPIO4",
                pin_type=PinType.I2C_SDA,
                supported_features=["I2C"],
                max_current_source_ma=12.0,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(
                pin_id="GPIO5",
                pin_type=PinType.I2C_SCL,
                supported_features=["I2C"],
                max_current_source_ma=12.0,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(
                pin_id="GPIO12",
                pin_type=PinType.GPIO_OUT,
                supported_features=["PWM"],
                max_current_source_ma=12.0,
                internal_pullup_enabled=False,
                active_state=ActiveState.NONE,
            ),
            Pin(
                pin_id="GPIO13",
                pin_type=PinType.GPIO_IN,
                supported_features=[],
                max_current_source_ma=None,
                internal_pullup_enabled=True,
                active_state=ActiveState.NONE,
            ),
        ],
    )


def ina219_manifest() -> ComponentManifest:
    """INA219 current/power monitor — 3.3 V I2C sensor at address 0x40."""
    return ComponentManifest(
        component_id="sens_ina219",
        name="INA219 Current/Power Monitor",
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.0,
            max_operating_voltage=5.5,
            logic_level_voltage=3.3,
            max_current_draw_ma=1.0,
        ),
        default_i2c_address="0x40",
        pins=[
            Pin(pin_id="VCC", pin_type=PinType.POWER),
            Pin(pin_id="GND", pin_type=PinType.GND),
            Pin(
                pin_id="I2C_SDA",
                pin_type=PinType.I2C_SDA,
                supported_features=["I2C"],
            ),
            Pin(
                pin_id="I2C_SCL",
                pin_type=PinType.I2C_SCL,
                supported_features=["I2C"],
            ),
        ],
    )


def mock_manifests() -> dict[str, ComponentManifest]:
    """Return all mock manifests keyed by component_id."""
    mcu = mcu_rp2040_manifest()
    sensor = ina219_manifest()
    return {mcu.component_id: mcu, sensor.component_id: sensor}
