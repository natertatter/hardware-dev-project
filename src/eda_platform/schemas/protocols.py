"""Protocol profile derivation and pin filtering for multi-protocol components."""

from eda_platform.schemas.component_manifest import ComponentManifest, Pin
from eda_platform.schemas.enums import PinType

# Canonical communication protocol identifiers used across UI and auto-wire.
COMMUNICATION_PROTOCOLS = ("I2C", "SPI", "UART", "PWM", "GPIO")

_I2C_PIN_TYPES = {PinType.I2C_SDA, PinType.I2C_SCL}
_SPI_PIN_TYPES = {PinType.SPI_MOSI, PinType.SPI_MISO, PinType.SPI_SCK, PinType.SPI_CS}
_UART_PIN_TYPES = {PinType.UART_TX, PinType.UART_RX}
_POWER_GND_TYPES = {PinType.POWER, PinType.GND}


def _power_gnd_pin_ids(manifest: ComponentManifest) -> list[str]:
    return [p.pin_id for p in manifest.pins if p.pin_type in _POWER_GND_TYPES]


def _pin_ids_by_types(manifest: ComponentManifest, pin_types: set[PinType]) -> list[str]:
    return [p.pin_id for p in manifest.pins if p.pin_type in pin_types]


def derive_protocol_profiles(manifest: ComponentManifest) -> dict[str, list[str]]:
    """Infer protocol → active pin_id lists from a manifest's pin definitions.

    POWER and GND pins are included in every profile. Profiles are only created
    when the manifest has enough pins to support that bus (e.g. both SDA+SCL for I2C).
    """
    if manifest.protocol_profiles:
        return dict(manifest.protocol_profiles)

    power_gnd = _power_gnd_pin_ids(manifest)
    profiles: dict[str, list[str]] = {}

    i2c_pins = _pin_ids_by_types(manifest, _I2C_PIN_TYPES)
    if len(i2c_pins) >= 2:
        profiles["I2C"] = power_gnd + i2c_pins

    spi_pins = _pin_ids_by_types(manifest, _SPI_PIN_TYPES)
    if len({p.pin_type for p in manifest.pins if p.pin_type in _SPI_PIN_TYPES}) >= 3:
        profiles["SPI"] = power_gnd + spi_pins

    uart_pins = _pin_ids_by_types(manifest, _UART_PIN_TYPES)
    if len(uart_pins) >= 2:
        profiles["UART"] = power_gnd + uart_pins

    pwm_pins = [
        p.pin_id
        for p in manifest.pins
        if p.pin_type == PinType.GPIO_OUT and "PWM" in (p.supported_features or [])
    ]
    if pwm_pins:
        profiles["PWM"] = power_gnd + pwm_pins

    gpio_pins = [
        p.pin_id
        for p in manifest.pins
        if p.pin_type in {PinType.GPIO_IN, PinType.GPIO_OUT, PinType.ANALOG_IN}
        and p.pin_type not in _I2C_PIN_TYPES
        and p.pin_type not in _SPI_PIN_TYPES
        and p.pin_type not in _UART_PIN_TYPES
    ]
    if gpio_pins and not profiles:
        profiles["GPIO"] = power_gnd + gpio_pins

    return profiles


def available_protocols(manifest: ComponentManifest) -> list[str]:
    """Return sorted list of communication protocols supported by this component."""
    profiles = derive_protocol_profiles(manifest)
    return sorted(profiles.keys(), key=lambda p: COMMUNICATION_PROTOCOLS.index(p) if p in COMMUNICATION_PROTOCOLS else 99)


def default_protocol(manifest: ComponentManifest) -> str | None:
    """Pick the default protocol for a newly placed component."""
    protocols = available_protocols(manifest)
    if not protocols:
        return None
    if manifest.default_protocol and manifest.default_protocol in protocols:
        return manifest.default_protocol
    return protocols[0]


def pins_for_protocol(manifest: ComponentManifest, protocol: str | None) -> list[Pin]:
    """Return the subset of manifest pins active for the given protocol.

    When protocol is None or the component has only one profile, all pins are shown.
    """
    profiles = derive_protocol_profiles(manifest)
    if not profiles or protocol is None:
        return list(manifest.pins)

    pin_ids = profiles.get(protocol)
    if pin_ids is None:
        return list(manifest.pins)

    active = set(pin_ids)
    return [p for p in manifest.pins if p.pin_id in active]
