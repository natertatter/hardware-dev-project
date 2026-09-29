import { describe, expect, it } from "vitest";

import { formatStepTiming } from "@/lib/timingProvenance";

describe("formatStepTiming", () => {
  it("joins a datasheet delay with its source", () => {
    expect(
      formatStepTiming({
        delay_ms: 100,
        source: "datasheet",
        note: "sens_ina219 operational_constraints.power_on_delay_ms",
      }),
    ).toBe("100 ms · datasheet");
  });

  it("labels a best-practice poll period", () => {
    expect(formatStepTiming({ period_ms: 20, source: "best_practice" })).toBe(
      "every 20 ms · best practice",
    );
  });

  it("returns an empty string when no timing fields are set", () => {
    expect(formatStepTiming({})).toBe("");
  });
});
