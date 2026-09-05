"""Map schematic logical pins to Raspberry Pi 4 platform resources."""

from dataclasses import dataclass

# Logical schematic pin names (from RP2040 mock manifests) → Pi 4 BCM GPIO numbers.
# The Firmware Engineer maps canvas MCU pins to the Pi 4 header used for testing.
LOGICAL_TO_BCM: dict[str, int] = {
    "GPIO4": 2,   # I2C1 SDA on Pi 40-pin header
    "GPIO5": 3,   # I2C1 SCL
    "GPIO12": 12,
    "GPIO13": 13,
    "I2C_SDA": 2,
    "I2C_SCL": 3,
}

I2C_DEVICE_PATH = "/dev/i2c-1"
I2C_BUS_NUMBER = 1


@dataclass(frozen=True)
class PlatformConfig:
    name: str = "rpi4"
    i2c_device_path: str = I2C_DEVICE_PATH
    i2c_bus_number: int = I2C_BUS_NUMBER


def bcm_for_logical_pin(pin_id: str) -> int | None:
    return LOGICAL_TO_BCM.get(pin_id)


def default_platform() -> PlatformConfig:
    return PlatformConfig()
