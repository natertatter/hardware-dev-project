import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type OnConnect,
} from "@xyflow/react";
import { create } from "zustand";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import type { ComponentManifest, HardwareNodeData } from "@/types/schemas";

export type HardwareFlowNode = Node<HardwareNodeData>;

interface SchematicState {
  projectId: string;
  nodes: HardwareFlowNode[];
  edges: Edge[];
  catalog: ComponentManifest[];
  hasSeededDemo: boolean;

  onNodesChange: (changes: NodeChange<HardwareFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: OnConnect;
  addNode: (manifest: ComponentManifest, position?: { x: number; y: number }) => void;
  setProjectId: (id: string) => void;
}

let nodeCounter = 0;

function nextNodeId(componentId: string): string {
  nodeCounter += 1;
  return `${componentId}_${nodeCounter}`;
}

function defaultPosition(index: number): { x: number; y: number } {
  return { x: 120 + index * 320, y: 120 + (index % 2) * 80 };
}

export const useSchematicStore = create<SchematicState>((set, get) => ({
  projectId: "schematic_project",
  nodes: [],
  edges: [],
  catalog: COMPONENT_CATALOG,
  hasSeededDemo: false,

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },

  onEdgesChange: (changes) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },

  onConnect: (connection: Connection) => {
    set({
      edges: addEdge(
        {
          ...connection,
          id: `edge_${connection.source}_${connection.sourceHandle}_${connection.target}_${connection.targetHandle}`,
        },
        get().edges
      ),
    });
  },

  addNode: (manifest, position) => {
    const { nodes } = get();
    const id = nextNodeId(manifest.component_id);
    const pos = position ?? defaultPosition(nodes.length);

    const newNode: HardwareFlowNode = {
      id,
      type: "hardware",
      position: pos,
      data: {
        manifest,
        label: manifest.name,
        assigned_i2c_address: manifest.default_i2c_address ?? null,
      },
    };

    set({ nodes: [...nodes, newNode] });
  },

  setProjectId: (id) => set({ projectId: id }),
}));

/**
 * Seed the canvas with an MCU and INA219 sensor for quick manual testing.
 *
 * Guarded by `hasSeededDemo` in the store state (not just `nodes.length === 0`
 * checked by the caller) because React 18 Strict Mode deliberately
 * double-invokes effects in development (`reactStrictMode: true` in
 * next.config.ts). A caller checking only `nodes.length === 0` from a render
 * closure can still fire twice before the first `addNode` call is reflected
 * in a new render, seeding duplicate nodes. Reading and flipping the guard
 * via `get()`/`set()` on the store itself makes the seed atomic and
 * idempotent regardless of call count, and resettable in tests via
 * `useSchematicStore.setState({ hasSeededDemo: false })`.
 */
export function seedDemoSchematic(): void {
  const store = useSchematicStore.getState();
  if (store.hasSeededDemo) return;
  useSchematicStore.setState({ hasSeededDemo: true });

  const mcu = store.catalog.find((c) => c.component_id === "mcu_rp2040");
  const sensor = store.catalog.find((c) => c.component_id === "sens_ina219");
  if (mcu) store.addNode(mcu, { x: 80, y: 160 });
  if (sensor) store.addNode(sensor, { x: 480, y: 160 });
}

if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
  // Dev-only console debug hook: window.__schematicStore.getState()
  (window as unknown as { __schematicStore: typeof useSchematicStore }).__schematicStore =
    useSchematicStore;
}
