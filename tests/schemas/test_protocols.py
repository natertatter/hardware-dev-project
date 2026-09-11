"""Tests for protocol profile derivation."""

from eda_platform.schemas import ComponentManifest, ComponentType, Pin, PinType, PowerRequirements
from eda_platform.schemas.protocols import (
    available_protocols,
    default_protocol,
    derive_protocol_profiles,
    pins_for_protocol,
)


def _bme280_manifest() -> ComponentManifest:
    return ComponentManifest(
        component_id="sens_bme280",
        name="BME280",
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=1.71,
            max_operating_voltage=3.6,
            logic_level_voltage=3.3,
            max_current_draw_ma=0.4,
        ),
        default_protocol="I2C",
        protocol_profiles={
            "I2C": ["VCC", "GND", "SDA", "SCL"],
            "SPI": ["VCC", "GND", "SDI", "SDO", "SCK", "CSB"],
        },
        pins=[
            Pin(pin_id="VCC", pin_type=PinType.POWER),
            Pin(pin_id="GND", pin_type=PinType.GND),
            Pin(pin_id="SDA", pin_type=PinType.I2C_SDA, supported_features=["I2C"]),
            Pin(pin_id="SCL", pin_type=PinType.I2C_SCL, supported_features=["I2C"]),
            Pin(pin_id="SDI", pin_type=PinType.SPI_MOSI, supported_features=["SPI"]),
            Pin(pin_id="SDO", pin_type=PinType.SPI_MISO, supported_features=["SPI"]),
            Pin(pin_id="SCK", pin_type=PinType.SPI_SCK, supported_features=["SPI"]),
            Pin(pin_id="CSB", pin_type=PinType.SPI_CS, supported_features=["SPI"]),
        ],
    )


def test_derive_protocol_profiles_from_explicit_mapping():
    manifest = _bme280_manifest()
    profiles = derive_protocol_profiles(manifest)
    assert set(profiles.keys()) == {"I2C", "SPI"}
    assert "SDA" in profiles["I2C"]
    assert "CSB" in profiles["SPI"]


def test_available_protocols_sorted():
    manifest = _bme280_manifest()
    assert available_protocols(manifest) == ["I2C", "SPI"]


def test_default_protocol_respects_manifest_default():
    manifest = _bme280_manifest()
    assert default_protocol(manifest) == "I2C"


def test_pins_for_protocol_filters_active_pins():
    manifest = _bme280_manifest()
    i2c_pins = pins_for_protocol(manifest, "I2C")
    pin_ids = {p.pin_id for p in i2c_pins}
    assert pin_ids == {"VCC", "GND", "SDA", "SCL"}
    assert "SDI" not in pin_ids


def test_derive_protocol_profiles_from_pin_types():
    manifest = ComponentManifest(
        component_id="sens_ina219",
        name="INA219",
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.0,
            max_operating_voltage=3.6,
            logic_level_voltage=3.3,
            max_current_draw_ma=1.0,
        ),
        pins=[
            Pin(pin_id="VCC", pin_type=PinType.POWER),
            Pin(pin_id="GND", pin_type=PinType.GND),
            Pin(pin_id="SDA", pin_type=PinType.I2C_SDA, supported_features=["I2C"]),
            Pin(pin_id="SCL", pin_type=PinType.I2C_SCL, supported_features=["I2C"]),
        ],
    )
    profiles = derive_protocol_profiles(manifest)
    assert "I2C" in profiles
    assert len(profiles) == 1
