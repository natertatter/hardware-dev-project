import { describe, expect, it } from "vitest";

import type { ComponentManifest } from "@/types/schemas";
import {
  availableProtocols,
  defaultProtocol,
  deriveProtocolProfiles,
  pinsForProtocol,
} from "@/utils/protocolProfiles";

const bme280: ComponentManifest = {
  component_id: "sens_bme280",
  name: "BME280",
  type: "SENSOR",
  power_requirements: {
    min_operating_voltage: 1.71,
    max_operating_voltage: 3.6,
    logic_level_voltage: 3.3,
    max_current_draw_ma: 0.4,
  },
  default_protocol: "I2C",
  protocol_profiles: {
    I2C: ["VCC", "GND", "SDA", "SCL"],
    SPI: ["VCC", "GND", "SDI", "SDO", "SCK", "CSB"],
  },
  pins: [
    { pin_id: "VCC", pin_type: "POWER" },
    { pin_id: "GND", pin_type: "GND" },
    { pin_id: "SDA", pin_type: "I2C_SDA", supported_features: ["I2C"] },
    { pin_id: "SCL", pin_type: "I2C_SCL", supported_features: ["I2C"] },
    { pin_id: "SDI", pin_type: "SPI_MOSI", supported_features: ["SPI"] },
    { pin_id: "SDO", pin_type: "SPI_MISO", supported_features: ["SPI"] },
    { pin_id: "SCK", pin_type: "SPI_SCK", supported_features: ["SPI"] },
    { pin_id: "CSB", pin_type: "SPI_CS", supported_features: ["SPI"] },
  ],
};

describe("protocolProfiles", () => {
  it("derives I2C and SPI profiles from explicit mapping", () => {
    const profiles = deriveProtocolProfiles(bme280);
    expect(Object.keys(profiles).sort()).toEqual(["I2C", "SPI"]);
  });

  it("returns default protocol from manifest", () => {
    expect(defaultProtocol(bme280)).toBe("I2C");
  });

  it("filters pins for selected protocol", () => {
    const pins = pinsForProtocol(bme280, "SPI");
    const ids = pins.map((p) => p.pin_id);
    expect(ids).toContain("SDI");
    expect(ids).not.toContain("SDA");
  });

  it("lists available protocols", () => {
    expect(availableProtocols(bme280)).toEqual(["I2C", "SPI"]);
  });
});
