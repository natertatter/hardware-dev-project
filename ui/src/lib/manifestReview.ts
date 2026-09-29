/** Edit helpers for the datasheet review loop (Horizon C1). */

import type {
  ComponentManifest,
  ComponentType,
  OperationalConstraints,
  Pin,
  PinType,
  PowerRequirements,
} from "@/types/schemas";
import { availableProtocols } from "@/utils/protocolProfiles";

export interface ExtractionIssue {
  severity: string;
  code: string;
  message: string;
  field?: string | null;
}

export const PIN_TYPES: PinType[] = [
  "POWER",
  "GND",
  "GPIO_IN",
  "GPIO_OUT",
  "I2C_SDA",
  "I2C_SCL",
  "SPI_MOSI",
  "SPI_MISO",
  "SPI_SCK",
  "SPI_CS",
  "UART_TX",
  "UART_RX",
  "ANALOG_IN",
];

const COMPONENT_ID_RE = /^[a-z0-9_]+$/;
const I2C_ADDRESS_RE = /^0x[0-9a-f]+$/;

export function featuresForPinType(pinType: PinType): string[] {
  switch (pinType) {
    case "I2C_SDA":
    case "I2C_SCL":
      return ["I2C"];
    case "SPI_MOSI":
    case "SPI_MISO":
    case "SPI_SCK":
    case "SPI_CS":
      return ["SPI"];
    case "UART_TX":
    case "UART_RX":
      return ["UART"];
    default:
      return [];
  }
}

/** Drop stale protocol profiles so pin edits re-derive the bus list. */
export function prepareReviewManifest(manifest: ComponentManifest): ComponentManifest {
  return syncProtocol({
    ...manifest,
    pins: manifest.pins.map((pin) => ({ ...pin })),
    power_requirements: { ...manifest.power_requirements },
    operational_constraints: manifest.operational_constraints
      ? { ...manifest.operational_constraints }
      : null,
  });
}

export function withName(manifest: ComponentManifest, name: string): ComponentManifest {
  return { ...manifest, name };
}

export function withComponentId(manifest: ComponentManifest, componentId: string): ComponentManifest {
  return { ...manifest, component_id: componentId.trim().toLowerCase() };
}

export function withType(manifest: ComponentManifest, type: ComponentType): ComponentManifest {
  return { ...manifest, type };
}

export function withPower(
  manifest: ComponentManifest,
  key: keyof PowerRequirements,
  value: number,
): ComponentManifest {
  return {
    ...manifest,
    power_requirements: { ...manifest.power_requirements, [key]: value },
  };
}

export function withI2cAddress(manifest: ComponentManifest, address: string): ComponentManifest {
  const trimmed = address.trim().toLowerCase();
  return { ...manifest, default_i2c_address: trimmed || null };
}

export function withConstraint(
  manifest: ComponentManifest,
  key: keyof OperationalConstraints,
  value: number | null,
): ComponentManifest {
  const current = manifest.operational_constraints ?? {};
  const next: OperationalConstraints = { ...current, [key]: value };
  const empty =
    next.power_on_delay_ms == null &&
    next.conversion_time_ms == null &&
    next.i2c_max_clock_hz == null;
  return { ...manifest, operational_constraints: empty ? null : next };
}

export function updatePin(
  manifest: ComponentManifest,
  index: number,
  patch: Partial<Pin>,
): ComponentManifest {
  const pins = manifest.pins.map((pin, i) => {
    if (i !== index) {
      return pin;
    }
    const next: Pin = { ...pin, ...patch };
    if (patch.pin_type && patch.pin_type !== pin.pin_type && patch.supported_features === undefined) {
      next.supported_features = featuresForPinType(patch.pin_type);
    }
    return next;
  });
  return syncProtocol({ ...manifest, pins });
}

export function addPin(manifest: ComponentManifest): ComponentManifest {
  const pin: Pin = { pin_id: "GPIO", pin_type: "GPIO_IN", supported_features: [] };
  return syncProtocol({ ...manifest, pins: [...manifest.pins, pin] });
}

export function removePin(manifest: ComponentManifest, index: number): ComponentManifest {
  return syncProtocol({
    ...manifest,
    pins: manifest.pins.filter((_, i) => i !== index),
  });
}

export function localCommitErrors(manifest: ComponentManifest): string[] {
  const errors: string[] = [];
  if (!COMPONENT_ID_RE.test(manifest.component_id)) {
    errors.push("Component id must be lowercase letters, digits, and underscores.");
  }
  if (!manifest.name.trim()) {
    errors.push("Name is required.");
  }
  const power = manifest.power_requirements;
  if (power.max_operating_voltage < power.min_operating_voltage) {
    errors.push("Max voltage must be greater than or equal to min voltage.");
  }
  if (manifest.pins.length < 1) {
    errors.push("At least one pin is required.");
  }
  const ids = manifest.pins.map((pin) => pin.pin_id.trim());
  if (ids.some((id) => !id)) {
    errors.push("Every pin needs an id.");
  }
  if (new Set(ids.filter(Boolean)).size !== ids.filter(Boolean).length) {
    errors.push("Pin ids must be unique.");
  }
  if (manifest.default_i2c_address && !I2C_ADDRESS_RE.test(manifest.default_i2c_address)) {
    errors.push("I2C address must be hex prefixed with 0x.");
  }
  return errors;
}

function syncProtocol(manifest: ComponentManifest): ComponentManifest {
  const derived: ComponentManifest = { ...manifest, protocol_profiles: null };
  const protocols = availableProtocols(derived);
  const defaultProtocol =
    manifest.default_protocol && protocols.includes(manifest.default_protocol)
      ? manifest.default_protocol
      : (protocols[0] ?? null);
  return { ...derived, default_protocol: defaultProtocol };
}
