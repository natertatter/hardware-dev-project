import { describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import type { HardwareNodeData } from "@/types/schemas";
import { buildSchematicDraft } from "@/utils/buildSchematicDraft";

function node(id: string, componentId: string): Node<HardwareNodeData> {
  const manifest = COMPONENT_CATALOG.find((c) => c.component_id === componentId)!;
  return {
    id,
    type: "hardware",
    position: { x: 0, y: 0 },
    data: { manifest },
  };
}

describe("buildSchematicDraft", () => {
  it("throws when no nodes are placed", () => {
    expect(() => buildSchematicDraft([], [], "p1")).toThrow(/at least one component/i);
  });

  it("returns empty nets for placement-only canvas", () => {
    const draft = buildSchematicDraft([node("mcu_1", "mcu_rp2040")], [], "p1");
    expect(draft.nets).toEqual([]);
    expect(draft.project_id).toBe("p1");
  });

  it("compiles wired schematics into nets", () => {
    const nodes = [node("mcu_1", "mcu_rp2040"), node("sensor_1", "sens_ina219")];
    const edges: Edge[] = [
      {
        id: "e1",
        source: "mcu_1",
        sourceHandle: "GND",
        target: "sensor_1",
        targetHandle: "GND",
      },
    ];
    const draft = buildSchematicDraft(nodes, edges, "wired");
    expect(draft.nets.length).toBeGreaterThan(0);
  });
});
