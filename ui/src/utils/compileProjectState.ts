import type { Edge, Node } from "@xyflow/react";
import type { HardwareNodeData } from "@/types/schemas";
import type { Net, NetConnection, NetType, PinType, ProjectState } from "@/types/schemas";

/** Canonical pin endpoint: one physical pin on one schematic node. */
export interface PinEndpoint {
  nodeId: string;
  pinId: string;
  pinType?: PinType;
}

const BUS_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "I2C_SDA",
  "I2C_SCL",
  "SPI_MOSI",
  "SPI_MISO",
  "SPI_SCK",
  "SPI_CS",
]);

/**
 * Union-Find (disjoint-set) for grouping electrically connected pin endpoints.
 * Two endpoints in the same connected component share one net.
 */
class UnionFind {
  private parent = new Map<string, string>();

  private key(endpoint: PinEndpoint): string {
    return `${endpoint.nodeId}::${endpoint.pinId}`;
  }

  find(endpoint: PinEndpoint): string {
    const k = this.key(endpoint);
    if (!this.parent.has(k)) {
      this.parent.set(k, k);
    }
    let root = k;
    while (this.parent.get(root) !== root) {
      root = this.parent.get(root)!;
    }
    // Path compression
    let current = k;
    while (current !== root) {
      const next = this.parent.get(current)!;
      this.parent.set(current, root);
      current = next;
    }
    return root;
  }

  union(a: PinEndpoint, b: PinEndpoint): void {
    const rootA = this.find(a);
    const rootB = this.find(b);
    if (rootA !== rootB) {
      this.parent.set(rootB, rootA);
    }
  }

  groups(): Map<string, PinEndpoint[]> {
    const result = new Map<string, PinEndpoint[]>();
    for (const k of this.parent.keys()) {
      const [nodeId, pinId] = k.split("::");
      const endpoint: PinEndpoint = { nodeId, pinId };
      const root = this.find(endpoint);
      const group = result.get(root) ?? [];
      group.push(endpoint);
      result.set(root, group);
    }
    return result;
  }
}

function lookupPinType(
  nodes: Node<HardwareNodeData>[],
  nodeId: string,
  pinId: string
): PinType {
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) {
    throw new Error(`Unknown node '${nodeId}' in edge`);
  }
  const pin = node.data.manifest.pins.find((p) => p.pin_id === pinId);
  if (!pin) {
    throw new Error(`Unknown pin '${pinId}' on node '${nodeId}'`);
  }
  return pin.pin_type;
}

function inferNetType(pinTypes: PinType[]): NetType {
  if (pinTypes.includes("GND")) return "GND";
  if (pinTypes.includes("POWER")) return "POWER";
  if (pinTypes.some((t) => BUS_PIN_TYPES.has(t))) return "BUS";
  return "SIGNAL";
}

function netName(netType: NetType, index: number, pinTypes: PinType[]): string {
  if (netType === "GND") return `net_gnd_${index}`;
  if (netType === "POWER") return `net_vcc_${index}`;
  if (netType === "BUS") {
    if (pinTypes.includes("I2C_SDA") || pinTypes.includes("I2C_SCL")) {
      return `net_i2c_${index}`;
    }
    return `net_bus_${index}`;
  }
  return `net_signal_${index}`;
}

/**
 * Compile React Flow nodes/edges into a backend-compliant ProjectState.
 *
 * Uses Union-Find to group point-to-point edges into electrical nets:
 * each connected component of pin endpoints becomes one net.
 */
export function compileProjectState(
  nodes: Node<HardwareNodeData>[],
  edges: Edge[],
  projectId: string,
): ProjectState {
  const uf = new UnionFind();

  // Seed every placed node's pins so unconnected pins can still appear if needed.
  for (const node of nodes) {
    for (const pin of node.data.manifest.pins) {
      uf.find({ nodeId: node.id, pinId: pin.pin_id });
    }
  }

  // Union endpoints connected by each React Flow edge.
  for (const edge of edges) {
    if (!edge.sourceHandle || !edge.targetHandle) {
      throw new Error(
        `Edge '${edge.id}' is missing sourceHandle or targetHandle — pin-level handles are required`
      );
    }
    const source: PinEndpoint = {
      nodeId: edge.source,
      pinId: edge.sourceHandle,
    };
    const target: PinEndpoint = {
      nodeId: edge.target,
      pinId: edge.targetHandle,
    };
    uf.union(source, target);
  }

  // Collect only groups with >= 2 endpoints (actual nets with connections).
  const rawGroups = uf.groups();
  const connectedGroups: PinEndpoint[][] = [];

  for (const group of rawGroups.values()) {
    const enriched = group.map((ep) => ({
      ...ep,
      pinType: lookupPinType(nodes, ep.nodeId, ep.pinId),
    }));
    if (enriched.length >= 2) {
      connectedGroups.push(enriched);
    }
  }

  // Build ProjectState.nodes
  const projectNodes = nodes.map((node) => ({
    node_id: node.id,
    component_id: node.data.manifest.component_id,
    ...(node.data.assigned_i2c_address != null
      ? { assigned_i2c_address: node.data.assigned_i2c_address }
      : node.data.manifest.default_i2c_address != null
        ? { assigned_i2c_address: node.data.manifest.default_i2c_address }
        : {}),
    ...(node.data.selected_protocol != null
      ? { selected_protocol: node.data.selected_protocol }
      : {}),
  }));

  // Build ProjectState.nets from connected components
  const typeCounters: Record<NetType, number> = {
    POWER: 0,
    GND: 0,
    SIGNAL: 0,
    BUS: 0,
  };

  const nets: Net[] = connectedGroups.map((group) => {
    const pinTypes = group.map((ep) => ep.pinType as PinType);
    const netType = inferNetType(pinTypes);
    const index = typeCounters[netType]++;
    const connections: NetConnection[] = group.map((ep) => ({
      node_id: ep.nodeId,
      pin_id: ep.pinId,
    }));
    return {
      net_id: netName(netType, index, pinTypes),
      net_type: netType,
      connections,
    };
  });

  if (projectNodes.length === 0) {
    throw new Error("Cannot compile ProjectState: no nodes on canvas");
  }

  // The backend ProjectState schema requires nets to be non-empty
  // (Pydantic `Field(..., min_length=1)`). Placing nodes without wiring any
  // pins together compiles to zero nets, which is not a valid ProjectState —
  // fail loudly here rather than silently returning non-compliant JSON.
  if (nets.length === 0) {
    throw new Error(
      "Cannot compile ProjectState: no nets found — wire at least one pin-to-pin connection before validating"
    );
  }

  return {
    project_id: projectId,
    nodes: projectNodes,
    nets,
  };
}
