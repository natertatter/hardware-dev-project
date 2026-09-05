import { create } from "zustand";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";

import { autoWireProjectState, fetchManifests, validateProjectState } from "@/lib/api";
import type { CatalogEntry, HardwareNodeData } from "@/types/schemas";
import { compileProjectState } from "@/utils/compileProjectState";
import { decompileProjectState } from "@/utils/decompileProjectState";

export type ValidationStatus = "idle" | "validating" | "pass" | "fail" | "error";

export interface ValidationIssueView {
  rule: string;
  message: string;
  node_id?: string;
  net_id?: string;
}

interface SchematicState {
  nodes: Node<HardwareNodeData>[];
  edges: Edge[];
  catalog: CatalogEntry[];
  catalogLoaded: boolean;
  validationStatus: ValidationStatus;
  validationIssues: ValidationIssueView[];
  validationMessage: string | null;
  schematicApproved: boolean;
  actions: {
    onNodesChange: (changes: NodeChange<Node<HardwareNodeData>>[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    onConnect: (connection: Connection) => void;
    addNodeFromCatalog: (entry: CatalogEntry) => void;
    loadCatalog: () => Promise<void>;
    validateArchitecture: () => Promise<void>;
    autoWire: () => Promise<void>;
    approveSchematic: () => void;
    resetApproval: () => void;
  };
}

let nodeCounter = 0;

export const useSchematicStore = create<SchematicState>((set, get) => ({
  nodes: [],
  edges: [],
  catalog: [],
  catalogLoaded: false,
  validationStatus: "idle",
  validationIssues: [],
  validationMessage: null,
  schematicApproved: false,
  actions: {
    onNodesChange: (changes) => {
      set({
        nodes: applyNodeChanges(changes, get().nodes),
        schematicApproved: false,
      });
    },
    onEdgesChange: (changes) => {
      set({
        edges: applyEdgeChanges(changes, get().edges),
        schematicApproved: false,
      });
    },
    onConnect: (connection) => {
      set({
        edges: addEdge(
          {
            ...connection,
            id: `edge-${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
          },
          get().edges,
        ),
        schematicApproved: false,
      });
    },
    addNodeFromCatalog: (entry) => {
      nodeCounter += 1;
      const newNode: Node<HardwareNodeData> = {
        id: `node-${entry.manifest.component_id}-${nodeCounter}`,
        type: "hardware",
        position: { x: 120 + nodeCounter * 40, y: 80 + nodeCounter * 30 },
        data: {
          label: entry.label,
          manifest: entry.manifest,
        },
      };
      set({
        nodes: [...get().nodes, newNode],
        schematicApproved: false,
      });
    },
    loadCatalog: async () => {
      try {
        const manifests = await fetchManifests();
        const catalog: CatalogEntry[] = manifests.map((manifest) => ({
          label: manifest.name,
          manifest,
        }));
        set({ catalog, catalogLoaded: true });
      } catch (err) {
        console.error("Failed to load manifest catalog:", err);
      }
    },
    validateArchitecture: async () => {
      set({ validationStatus: "validating", validationMessage: null });
      const projectState = compileProjectState(get().nodes, get().edges);
      try {
        const result = await validateProjectState(projectState);
        if (result.valid) {
          set({
            validationStatus: "pass",
            validationIssues: [],
            validationMessage: "Architecture passed all validation rules.",
          });
        } else {
          set({
            validationStatus: "fail",
            validationIssues: result.errors.map((issue) => ({
              rule: issue.rule,
              message: issue.message,
              node_id: issue.node_id ?? undefined,
              net_id: issue.net_id ?? undefined,
            })),
            validationMessage: `${result.errors.length} issue(s) found.`,
          });
        }
      } catch (err) {
        set({
          validationStatus: "error",
          validationIssues: [],
          validationMessage: err instanceof Error ? err.message : "Validation request failed.",
        });
      }
    },
    autoWire: async () => {
      const { nodes: currentNodes, edges: currentEdges, catalog } = get();
      let projectState;
      try {
        projectState = compileProjectState(currentNodes, currentEdges);
      } catch {
        // Auto-wire can run on unconnected nodes — send placement-only state.
        projectState = {
          project_id: "schematic_project",
          nodes: currentNodes.map((node) => ({
            node_id: node.id,
            component_id: node.data.manifest.component_id,
            ...(node.data.assigned_i2c_address != null
              ? { assigned_i2c_address: node.data.assigned_i2c_address }
              : node.data.manifest.default_i2c_address != null
                ? { assigned_i2c_address: node.data.manifest.default_i2c_address }
                : {}),
          })),
          nets: [],
        };
      }
      try {
        const response = await autoWireProjectState(projectState);
        const manifests = Object.fromEntries(
          catalog.map((entry) => [entry.manifest.component_id, entry.manifest]),
        );
        const { nodes, edges } = decompileProjectState(
          response.project_state,
          manifests,
          currentNodes,
        );
        set({ nodes, edges, schematicApproved: false, validationStatus: "idle" });
      } catch (err) {
        set({
          validationStatus: "error",
          validationMessage: err instanceof Error ? err.message : "Auto-wire failed.",
        });
      }
    },
    approveSchematic: () => {
      if (get().validationStatus === "pass") {
        set({ schematicApproved: true });
      }
    },
    resetApproval: () => set({ schematicApproved: false }),
  },
}));
