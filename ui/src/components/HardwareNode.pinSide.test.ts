import { describe, expect, it } from "vitest";

import { pinSide } from "@/components/HardwareNode";
import { COMPONENT_CATALOG } from "@/data/mockCatalog";

describe("pinSide", () => {
  it("places MCU I2C and power rails on the right (source side)", () => {
    const mcu = COMPONENT_CATALOG.find((m) => m.component_id === "mcu_rp2040")!;
    const sda = mcu.pins.find((p) => p.pin_id === "GPIO4")!;
    const pwr = mcu.pins.find((p) => p.pin_id === "3V3_OUT")!;
    expect(pinSide(mcu, sda)).toBe("right");
    expect(pinSide(mcu, pwr)).toBe("right");
  });

  it("places sensor I2C and power inputs on the left (target side)", () => {
    const sensor = COMPONENT_CATALOG.find((m) => m.component_id === "sens_ina219")!;
    const sda = sensor.pins.find((p) => p.pin_id === "I2C_SDA")!;
    const vcc = sensor.pins.find((p) => p.pin_id === "VCC")!;
    expect(pinSide(sensor, sda)).toBe("left");
    expect(pinSide(sensor, vcc)).toBe("left");
  });
});
