import { describe, expect, it } from "vitest";

import { pinSide } from "@/utils/pinSide";
import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import type { ComponentManifest } from "@/types/schemas";

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

  it("places MCU SPI pins on the right (source side)", () => {
    const mcu = COMPONENT_CATALOG.find((m) => m.component_id === "mcu_rp2040")!;
    const types = ["SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_CS"] as const;
    for (const pinType of types) {
      const pin = mcu.pins.find((p) => p.pin_type === pinType)!;
      expect(pinSide(mcu, pin)).toBe("right");
    }
  });

  it("places sensor SPI pins on the left (target side)", () => {
    const sensor: ComponentManifest = {
      component_id: "sens_bme280",
      name: "BME280",
      type: "SENSOR",
      power_requirements: {
        min_operating_voltage: 1.71,
        max_operating_voltage: 3.6,
        logic_level_voltage: 3.3,
        max_current_draw_ma: 0.4,
      },
      pins: [
        { pin_id: "VCC", pin_type: "POWER" },
        { pin_id: "GND", pin_type: "GND" },
        { pin_id: "SDI", pin_type: "SPI_MOSI" },
        { pin_id: "SDO", pin_type: "SPI_MISO" },
        { pin_id: "SCK", pin_type: "SPI_SCK" },
        { pin_id: "CSB", pin_type: "SPI_CS" },
      ],
    };
    for (const pin of sensor.pins.filter((p) => p.pin_type.startsWith("SPI_"))) {
      expect(pinSide(sensor, pin)).toBe("left");
    }
  });
});
