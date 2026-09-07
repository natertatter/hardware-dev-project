/** Protocol profile derivation — mirrors backend schemas/protocols.py */

import type { ComponentManifest, Pin, PinType } from "@/types/schemas";

const I2C_PIN_TYPES: ReadonlySet<PinType> = new Set(["I2C_SDA", "I2C_SCL"]);
const SPI_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "SPI_MOSI",
  "SPI_MISO",
  "SPI_SCK",
  "SPI_CS",
]);
const UART_PIN_TYPES: ReadonlySet<PinType> = new Set(["UART_TX", "UART_RX"]);
const POWER_GND_TYPES: ReadonlySet<PinType> = new Set(["POWER", "GND"]);

function powerGndPinIds(manifest: ComponentManifest): string[] {
  return manifest.pins.filter((p) => POWER_GND_TYPES.has(p.pin_type)).map((p) => p.pin_id);
}

function pinIdsByTypes(manifest: ComponentManifest, types: ReadonlySet<PinType>): string[] {
  return manifest.pins.filter((p) => types.has(p.pin_type)).map((p) => p.pin_id);
}

export function deriveProtocolProfiles(manifest: ComponentManifest): Record<string, string[]> {
  if (manifest.protocol_profiles) {
    return manifest.protocol_profiles;
  }

  const powerGnd = powerGndPinIds(manifest);
  const profiles: Record<string, string[]> = {};

  const i2cPins = pinIdsByTypes(manifest, I2C_PIN_TYPES);
  if (i2cPins.length >= 2) {
    profiles.I2C = [...powerGnd, ...i2cPins];
  }

  const spiPinTypes = new Set(
    manifest.pins.filter((p) => SPI_PIN_TYPES.has(p.pin_type)).map((p) => p.pin_type)
  );
  if (spiPinTypes.size >= 3) {
    profiles.SPI = [...powerGnd, ...pinIdsByTypes(manifest, SPI_PIN_TYPES)];
  }

  const uartPins = pinIdsByTypes(manifest, UART_PIN_TYPES);
  if (uartPins.length >= 2) {
    profiles.UART = [...powerGnd, ...uartPins];
  }

  const pwmPins = manifest.pins
    .filter((p) => p.pin_type === "GPIO_OUT" && p.supported_features?.includes("PWM"))
    .map((p) => p.pin_id);
  if (pwmPins.length > 0) {
    profiles.PWM = [...powerGnd, ...pwmPins];
  }

  const gpioPins = manifest.pins
    .filter(
      (p) =>
        (p.pin_type === "GPIO_IN" ||
          p.pin_type === "GPIO_OUT" ||
          p.pin_type === "ANALOG_IN") &&
        !I2C_PIN_TYPES.has(p.pin_type) &&
        !SPI_PIN_TYPES.has(p.pin_type) &&
        !UART_PIN_TYPES.has(p.pin_type)
    )
    .map((p) => p.pin_id);
  if (gpioPins.length > 0 && Object.keys(profiles).length === 0) {
    profiles.GPIO = [...powerGnd, ...gpioPins];
  }

  return profiles;
}

export function availableProtocols(manifest: ComponentManifest): string[] {
  return Object.keys(deriveProtocolProfiles(manifest)).sort();
}

export function defaultProtocol(manifest: ComponentManifest): string | null {
  const protocols = availableProtocols(manifest);
  if (protocols.length === 0) return null;
  if (manifest.default_protocol && protocols.includes(manifest.default_protocol)) {
    return manifest.default_protocol;
  }
  return protocols[0];
}

export function pinsForProtocol(manifest: ComponentManifest, protocol: string | null): Pin[] {
  const profiles = deriveProtocolProfiles(manifest);
  if (!profiles || protocol === null) {
    return manifest.pins;
  }
  const pinIds = profiles[protocol];
  if (!pinIds) {
    return manifest.pins;
  }
  const active = new Set(pinIds);
  return manifest.pins.filter((p) => active.has(p.pin_id));
}
