import { describe, expect, it } from "vitest";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import { decompileProjectState } from "@/utils/decompileProjectState";

describe("decompileProjectState auto-wire", () => {
  it("creates visible edges for template I2C nets", () => {
    const manifests = Object.fromEntries(
      COMPONENT_CATALOG.map((manifest) => [manifest.component_id, manifest]),
    );

    const projectState = {
      project_id: "test",
      nodes: [
        { node_id: "node-mcu_rp2040-1", component_id: "mcu_rp2040" },
        { node_id: "node-sens_ina219-2", component_id: "sens_ina219" },
      ],
      nets: [
        {
          net_id: "auto_node-sens_ina219-2_sda",
          net_type: "BUS" as const,
          connections: [
            { node_id: "node-mcu_rp2040-1", pin_id: "GPIO4" },
            { node_id: "node-sens_ina219-2", pin_id: "I2C_SDA" },
          ],
        },
        {
          net_id: "auto_node-sens_ina219-2_scl",
          net_type: "BUS" as const,
          connections: [
            { node_id: "node-mcu_rp2040-1", pin_id: "GPIO5" },
            { node_id: "node-sens_ina219-2", pin_id: "I2C_SCL" },
          ],
        },
      ],
    };

    const { edges } = decompileProjectState(projectState, manifests);

    expect(edges).toHaveLength(2);
    expect(edges[0]).toMatchObject({
      type: "smoothstep",
      source: "node-mcu_rp2040-1",
      sourceHandle: "GPIO4",
      target: "node-sens_ina219-2",
      targetHandle: "I2C_SDA",
    });
  });
});
