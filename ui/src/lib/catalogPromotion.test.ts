import { describe, expect, it } from "vitest";

import { unpromotedExamples } from "@/lib/catalogPromotion";

describe("unpromotedExamples", () => {
  it("keeps templates that have no production file", () => {
    const pending = unpromotedExamples([
      { component_id: "mcu_rp2040", name: "Pico", type: "MCU", promoted: true },
      { component_id: "sens_bme280", name: "BME280", type: "SENSOR", promoted: false },
    ]);
    expect(pending.map((item) => item.component_id)).toEqual(["sens_bme280"]);
  });
});
