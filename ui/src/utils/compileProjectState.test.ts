import { describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import type { HardwareNodeData } from "@/types/schemas";
import { compileProjectState } from "@/utils/compileProjectState";

function makeNode(
  id: string,
  componentId: string,
  assignedAddress?: string
): Node<HardwareNodeData> {
  const manifest = COMPONENT_CATALOG.find((c) => c.component_id === componentId)!;
  return {
    id,
    type: "hardware",
    position: { x: 0, y: 0 },
    data: {
      manifest,
      assigned_i2c_address: assignedAddress ?? manifest.default_i2c_address ?? null,
    },
  };
}

describe("compileProjectState", () => {
  it("compiles valid I2C wiring into ProjectState", () => {
    const nodes = [
      makeNode("mcu_1", "mcu_rp2040"),
      makeNode("sensor_1", "sens_ina219", "0x40"),
    ];
    const edges: Edge[] = [
      {
        id: "e1",
        source: "mcu_1",
        sourceHandle: "3V3_OUT",
        target: "sensor_1",
        targetHandle: "VCC",
      },
      {
        id: "e2",
        source: "mcu_1",
        sourceHandle: "GND",
        target: "sensor_1",
        targetHandle: "GND",
      },
      {
        id: "e3",
        source: "mcu_1",
        sourceHandle: "GPIO4",
        target: "sensor_1",
        targetHandle: "I2C_SDA",
      },
      {
        id: "e4",
        source: "mcu_1",
        sourceHandle: "GPIO5",
        target: "sensor_1",
        targetHandle: "I2C_SCL",
      },
    ];

    const state = compileProjectState(nodes, edges, "test_project");

    expect(state.project_id).toBe("test_project");
    expect(state.nodes).toHaveLength(2);
    expect(state.nodes[0]).toMatchObject({
      node_id: "mcu_1",
      component_id: "mcu_rp2040",
    });
    expect(state.nodes[1]).toMatchObject({
      node_id: "sensor_1",
      component_id: "sens_ina219",
      assigned_i2c_address: "0x40",
    });

    expect(state.nets).toHaveLength(4);

    const powerNet = state.nets.find((n) => n.net_type === "POWER");
    expect(powerNet?.connections).toEqual(
      expect.arrayContaining([
        { node_id: "mcu_1", pin_id: "3V3_OUT" },
        { node_id: "sensor_1", pin_id: "VCC" },
      ])
    );

    const gndNet = state.nets.find((n) => n.net_type === "GND");
    expect(gndNet?.connections).toHaveLength(2);

    const busNets = state.nets.filter((n) => n.net_type === "BUS");
    expect(busNets).toHaveLength(2);
  });

  it("merges transitive connections into one net via union-find", () => {
    const nodes = [
      makeNode("mcu_1", "mcu_rp2040"),
      makeNode("sensor_1", "sens_ina219"),
      makeNode("sensor_2", "sens_ina219", "0x41"),
    ];
    // Chain: mcu GND -> sensor_1 GND -> sensor_2 GND (via two edges)
    const edges: Edge[] = [
      {
        id: "e1",
        source: "mcu_1",
        sourceHandle: "GND",
        target: "sensor_1",
        targetHandle: "GND",
      },
      {
        id: "e2",
        source: "sensor_1",
        sourceHandle: "GND",
        target: "sensor_2",
        targetHandle: "GND",
      },
    ];

    const state = compileProjectState(nodes, edges, "test_project");
    const gndNets = state.nets.filter((n) => n.net_type === "GND");
    expect(gndNets).toHaveLength(1);
    expect(gndNets[0].connections).toHaveLength(3);
  });

  it("throws when edge is missing handle ids", () => {
    const nodes = [makeNode("mcu_1", "mcu_rp2040")];
    const edges: Edge[] = [
      { id: "e1", source: "mcu_1", target: "mcu_1" },
    ];
    expect(() => compileProjectState(nodes, edges, "test_project")).toThrow("missing sourceHandle");
  });

  it("throws when nodes are placed but nothing is wired (no nets)", () => {
    // Reflects the real UI flow: two nodes dropped on the canvas, then
    // "Validate Architecture" clicked before drawing any edges. The result
    // must not be a ProjectState with an empty `nets` array, since the
    // backend schema requires at least one net.
    const nodes = [
      makeNode("mcu_1", "mcu_rp2040"),
      makeNode("sensor_1", "sens_ina219"),
    ];
    expect(() => compileProjectState(nodes, [], "test_project")).toThrow("no nets found");
  });

  it("throws when called with zero nodes", () => {
    expect(() => compileProjectState([], [], "test_project")).toThrow("no nodes on canvas");
  });
});
