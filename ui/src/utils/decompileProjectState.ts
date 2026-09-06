import type { Edge, Node } from "@xyflow/react";

import type { ComponentManifest, HardwareNodeData, ProjectState } from "@/types/schemas";

/**
 * Convert backend ProjectState nets into React Flow nodes/edges for canvas display.
 * Preserves existing node positions when provided.
 */
export function decompileProjectState(
  projectState: ProjectState,
  manifests: Record<string, ComponentManifest>,
  existingNodes: Node<HardwareNodeData>[] = []
): { nodes: Node<HardwareNodeData>[]; edges: Edge[] } {
  const positionById = new Map(existingNodes.map((n) => [n.id, n.position]));

  const nodes: Node<HardwareNodeData>[] = projectState.nodes.map((psNode, index) => {
    const manifest = manifests[psNode.component_id];
    if (!manifest) {
      throw new Error(`Unknown component_id '${psNode.component_id}' during decompile`);
    }

    const position = positionById.get(psNode.node_id) ?? {
      x: 80 + index * 320,
      y: 160,
    };

    return {
      id: psNode.node_id,
      type: "hardware",
      position,
      data: {
        manifest,
        label: manifest.name,
        assigned_i2c_address: psNode.assigned_i2c_address ?? manifest.default_i2c_address ?? null,
      },
    };
  });

  const edges: Edge[] = [];
  let edgeCounter = 0;

  for (const net of projectState.nets) {
    const conns = net.connections;
    // Chain connections within a net: A-B, B-C, ...
    for (let i = 0; i < conns.length - 1; i++) {
      const a = conns[i];
      const b = conns[i + 1];
      edgeCounter += 1;
      edges.push({
        id: `edge_${net.net_id}_${edgeCounter}`,
        type: "smoothstep",
        source: a.node_id,
        sourceHandle: a.pin_id,
        target: b.node_id,
        targetHandle: b.pin_id,
        style: { stroke: "var(--lab-border)", strokeWidth: 2 },
      });
    }
  }

  return { nodes, edges };
}
