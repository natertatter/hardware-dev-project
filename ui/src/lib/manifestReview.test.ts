import { describe, expect, it } from "vitest";

import {
  addPin,
  localCommitErrors,
  prepareReviewManifest,
  removePin,
  updatePin,
  withComponentId,
  withConstraint,
  withI2cAddress,
  withPower,
} from "@/lib/manifestReview";
import type { ComponentManifest } from "@/types/schemas";

function draft(): ComponentManifest {
  return {
    component_id: "sens_review",
    name: "Review Sensor",
    type: "SENSOR",
    power_requirements: {
      min_operating_voltage: 1.71,
      max_operating_voltage: 3.6,
      logic_level_voltage: 1.8,
      max_current_draw_ma: 0.4,
    },
    default_i2c_address: "0x76",
    default_protocol: "I2C",
    protocol_profiles: {
      I2C: ["VCC", "GND", "SDA", "SCL"],
    },
    operational_constraints: { power_on_delay_ms: 2, conversion_time_ms: 10 },
    pins: [
      { pin_id: "VCC", pin_type: "POWER" },
      { pin_id: "GND", pin_type: "GND" },
      { pin_id: "SDA", pin_type: "I2C_SDA", supported_features: ["I2C"] },
      { pin_id: "SCL", pin_type: "I2C_SCL", supported_features: ["I2C"] },
    ],
  };
}

describe("manifest review edits", () => {
  it("clears stale protocol profiles and keeps a valid default", () => {
    const prepared = prepareReviewManifest(draft());
    expect(prepared.protocol_profiles).toBeNull();
    expect(prepared.default_protocol).toBe("I2C");
    expect(prepared.pins).toHaveLength(4);
  });

  it("applies electrical and timing edits", () => {
    let manifest = withPower(draft(), "max_operating_voltage", 3.3);
    manifest = withI2cAddress(manifest, "0X77");
    manifest = withConstraint(manifest, "conversion_time_ms", 8);
    manifest = withComponentId(manifest, "Sens_Reviewed");
    expect(manifest.power_requirements.max_operating_voltage).toBe(3.3);
    expect(manifest.default_i2c_address).toBe("0x77");
    expect(manifest.operational_constraints?.conversion_time_ms).toBe(8);
    expect(manifest.component_id).toBe("sens_reviewed");
    expect(localCommitErrors(manifest)).toEqual([]);
  });

  it("drops operational constraints when every timing field is cleared", () => {
    let manifest = withConstraint(draft(), "power_on_delay_ms", null);
    manifest = withConstraint(manifest, "conversion_time_ms", null);
    expect(manifest.operational_constraints).toBeNull();
  });

  it("re-derives the protocol after bus pins are removed", () => {
    let manifest = prepareReviewManifest(draft());
    manifest = updatePin(manifest, 2, { pin_id: "TX", pin_type: "UART_TX" });
    manifest = updatePin(manifest, 3, { pin_id: "RX", pin_type: "UART_RX" });
    expect(manifest.pins[2].supported_features).toEqual(["UART"]);
    expect(manifest.default_protocol).toBe("UART");
  });

  it("blocks commit when the id, voltage range, or pin ids are invalid", () => {
    const renamed = withComponentId(draft(), "Bad ID");
    expect(localCommitErrors(renamed)[0]).toMatch(/Component id/);

    const voltages = withPower(draft(), "min_operating_voltage", 5);
    expect(localCommitErrors(voltages).some((error) => error.includes("Max voltage"))).toBe(true);

    const added = addPin(prepareReviewManifest(draft()));
    const duplicate = updatePin(added, added.pins.length - 1, { pin_id: "SDA" });
    expect(localCommitErrors(duplicate).some((error) => error.includes("unique"))).toBe(true);

    const emptied = removePin(removePin(removePin(removePin(prepareReviewManifest(draft()), 0), 0), 0), 0);
    expect(localCommitErrors(emptied).some((error) => error.includes("At least one pin"))).toBe(true);
  });
});
