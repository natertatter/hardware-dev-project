import { describe, expect, it } from "vitest";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import type { ProjectState } from "@/types/schemas";
import { decompileProjectState } from "@/utils/decompileProjectState";

describe("decompileProjectState", () => {
  it("ignores synthetic _draft_ nets", () => {
    const manifests = Object.fromEntries(
      COMPONENT_CATALOG.map((m) => [m.component_id, m]),
    );
    const projectState: ProjectState = {
      project_id: "t",
      nodes: [
        { node_id: "mcu_1", component_id: "mcu_rp2040" },
        { node_id: "sensor_1", component_id: "sens_ina219", assigned_i2c_address: "0x40" },
      ],
      nets: [
        {
          net_id: "_draft_placeholder",
          net_type: "SIGNAL",
          connections: [
            { node_id: "mcu_1", pin_id: "GND" },
            { node_id: "sensor_1", pin_id: "GND" },
          ],
        },
        {
          net_id: "net_gnd",
          net_type: "GND",
          connections: [
            { node_id: "mcu_1", pin_id: "GND" },
            { node_id: "sensor_1", pin_id: "GND" },
          ],
        },
      ],
    };
    const { edges } = decompileProjectState(projectState, manifests);
    expect(edges.every((e) => !e.id.includes("_draft_placeholder"))).toBe(true);
    expect(edges.length).toBeGreaterThan(0);
  });
});
