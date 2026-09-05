import { describe, expect, it, beforeEach } from "vitest";

import { seedDemoSchematic, useSchematicStore } from "@/store/useSchematicStore";

describe("seedDemoSchematic", () => {
  beforeEach(() => {
    useSchematicStore.setState({ nodes: [], edges: [], hasSeededDemo: false });
  });

  it("seeds exactly one MCU and one sensor node", () => {
    seedDemoSchematic();
    const { nodes } = useSchematicStore.getState();
    expect(nodes).toHaveLength(2);
    expect(nodes.map((n) => n.data.manifest.component_id).sort()).toEqual([
      "mcu_rp2040",
      "sens_ina219",
    ]);
  });

  it("is idempotent across repeated calls (guards React Strict Mode double-invoke)", () => {
    seedDemoSchematic();
    seedDemoSchematic();
    seedDemoSchematic();

    const { nodes } = useSchematicStore.getState();
    // Must still be exactly 2 — not 4 or 6 — even though seedDemoSchematic
    // was invoked three times, simulating Strict Mode's double effect firing.
    expect(nodes).toHaveLength(2);
  });
});
