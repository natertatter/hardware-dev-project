import type { Edge, Node } from "@xyflow/react";

import type { HardwareNodeData, SchematicDraft } from "@/types/schemas";
import { compileProjectState } from "@/utils/compileProjectState";
import { defaultProtocol } from "@/utils/protocolProfiles";

/**
 * Build a schematic draft for the project persistence API.
 * Placement-only canvases send empty nets; the API adds a placeholder net.
 */
export function buildSchematicDraft(
  nodes: Node<HardwareNodeData>[],
  edges: Edge[],
  projectId: string,
): SchematicDraft {
  if (nodes.length === 0) {
    throw new Error("Place at least one component before saving the project.");
  }

  if (edges.length === 0) {
    return {
      project_id: projectId,
      nodes: nodes.map((node) => ({
        node_id: node.id,
        component_id: node.data.manifest.component_id,
        ...(node.data.assigned_i2c_address != null
          ? { assigned_i2c_address: node.data.assigned_i2c_address }
          : node.data.manifest.default_i2c_address != null
            ? { assigned_i2c_address: node.data.manifest.default_i2c_address }
            : {}),
        ...(node.data.selected_protocol != null
          ? { selected_protocol: node.data.selected_protocol }
          : defaultProtocol(node.data.manifest) != null
            ? { selected_protocol: defaultProtocol(node.data.manifest) }
            : {}),
      })),
      nets: [],
    };
  }

  const compiled = compileProjectState(nodes, edges, projectId);
  return {
    project_id: compiled.project_id,
    nodes: compiled.nodes,
    nets: compiled.nets,
  };
}
