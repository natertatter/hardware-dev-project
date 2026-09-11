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

import { autoWireProjectState, fetchManifests, generateFirmware, validateProjectState } from "@/lib/api";
import type { CatalogEntry, HardwareNodeData, ProjectState } from "@/types/schemas";
import { compileProjectState } from "@/utils/compileProjectState";
import { decompileProjectState } from "@/utils/decompileProjectState";
import { defaultProtocol, pinsForProtocol } from "@/utils/protocolProfiles";

export type ValidationStatus = "idle" | "validating" | "pass" | "fail" | "error";
export type FirmwareStatus = "idle" | "generating" | "success" | "error";
export type AutoWireStatus = "idle" | "wiring" | "success" | "error";

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
  catalogError: string | null;
  validationStatus: ValidationStatus;
  validationIssues: ValidationIssueView[];
  validationMessage: string | null;
  schematicApproved: boolean;
  firmwareStatus: FirmwareStatus;
  firmwareOutputDir: string | null;
  firmwareMessage: string | null;
  autoWireStatus: AutoWireStatus;
  autoWireMessage: string | null;
  actions: {
    onNodesChange: (changes: NodeChange<Node<HardwareNodeData>>[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    onConnect: (connection: Connection) => void;
    addNodeFromCatalog: (entry: CatalogEntry) => void;
    setNodeProtocol: (nodeId: string, protocol: string) => void;
    loadCatalog: () => Promise<void>;
    validateArchitecture: () => Promise<void>;
    autoWire: () => Promise<void>;
    approveSchematic: () => void;
    resetApproval: () => void;
    generateFirmware: () => Promise<void>;
  };
}

let nodeCounter = 0;

function resetApprovalAndFirmware() {
  return {
    schematicApproved: false,
    firmwareStatus: "idle" as FirmwareStatus,
    firmwareOutputDir: null,
    firmwareMessage: null,
  };
}

function resetWorkflowState() {
  return {
    ...resetApprovalAndFirmware(),
    autoWireStatus: "idle" as AutoWireStatus,
    autoWireMessage: null,
  };
}

function isUserDrivenNodeChange(changes: NodeChange<Node<HardwareNodeData>>[]): boolean {
  return changes.some(
    (change) =>
      change.type === "remove" ||
      change.type === "add" ||
      (change.type === "position" && "dragging" in change && change.dragging === false),
  );
}

function isUserDrivenEdgeChange(changes: EdgeChange[]): boolean {
  return changes.some((change) => change.type === "remove");
}

function placementOnlyProjectState(
  nodes: Node<HardwareNodeData>[],
): Pick<ProjectState, "project_id" | "nodes" | "nets"> {
  return {
    project_id: "schematic_project",
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

export const useSchematicStore = create<SchematicState>((set, get) => ({
  nodes: [],
  edges: [],
  catalog: [],
  catalogLoaded: false,
  catalogError: null,
  validationStatus: "idle",
  validationIssues: [],
  validationMessage: null,
  schematicApproved: false,
  firmwareStatus: "idle",
  firmwareOutputDir: null,
  firmwareMessage: null,
  autoWireStatus: "idle",
  autoWireMessage: null,
  actions: {
    onNodesChange: (changes) => {
      set({
        nodes: applyNodeChanges(changes, get().nodes),
        ...(isUserDrivenNodeChange(changes) ? resetWorkflowState() : {}),
      });
    },
    onEdgesChange: (changes) => {
      set({
        edges: applyEdgeChanges(changes, get().edges),
        ...(isUserDrivenEdgeChange(changes) ? resetWorkflowState() : {}),
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
        ...resetWorkflowState(),
      });
    },
    addNodeFromCatalog: (entry) => {
      nodeCounter += 1;
      const proto = defaultProtocol(entry.manifest);
      const newNode: Node<HardwareNodeData> = {
        id: `node-${entry.manifest.component_id}-${nodeCounter}`,
        type: "hardware",
        position: { x: 120 + nodeCounter * 40, y: 80 + nodeCounter * 30 },
        data: {
          label: entry.label,
          manifest: entry.manifest,
          ...(proto != null ? { selected_protocol: proto } : {}),
        },
      };
      set({
        nodes: [...get().nodes, newNode],
        ...resetWorkflowState(),
      });
    },
    setNodeProtocol: (nodeId, protocol) => {
      const { nodes, edges } = get();
      const targetNode = nodes.find((n) => n.id === nodeId);
      if (!targetNode) return;

      const activePinIds = new Set(
        pinsForProtocol(targetNode.data.manifest, protocol).map((p) => p.pin_id),
      );

      set({
        nodes: nodes.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, selected_protocol: protocol } }
            : node,
        ),
        edges: edges.filter((edge) => {
          if (edge.source === nodeId && edge.sourceHandle && !activePinIds.has(edge.sourceHandle)) {
            return false;
          }
          if (edge.target === nodeId && edge.targetHandle && !activePinIds.has(edge.targetHandle)) {
            return false;
          }
          return true;
        }),
        ...resetWorkflowState(),
      });
    },
    loadCatalog: async () => {
      set({ catalogLoaded: false, catalogError: null });
      try {
        const manifests = await fetchManifests();
        const catalog: CatalogEntry[] = manifests.map((manifest) => ({
          label: manifest.name,
          manifest,
        }));
        set({ catalog, catalogLoaded: true, catalogError: null });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load manifest catalog.";
        console.error("Failed to load manifest catalog:", err);
        set({ catalog: [], catalogLoaded: false, catalogError: message });
      }
    },
    validateArchitecture: async () => {
      set({
        validationStatus: "validating",
        validationMessage: null,
        validationIssues: [],
        autoWireStatus: "idle",
        autoWireMessage: null,
      });
      try {
        const projectState = compileProjectState(get().nodes, get().edges);
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
      if (catalog.length === 0) {
        set({
          autoWireStatus: "error",
          autoWireMessage: "Component catalog is empty. Load the catalog before auto-wiring.",
        });
        return;
      }
      set({
        autoWireStatus: "wiring",
        autoWireMessage: null,
        validationStatus: "idle",
        validationIssues: [],
        validationMessage: null,
      });

      let projectState: Pick<ProjectState, "project_id" | "nodes" | "nets">;
      if (currentEdges.length === 0) {
        projectState = placementOnlyProjectState(currentNodes);
      } else {
        try {
          projectState = compileProjectState(currentNodes, currentEdges);
        } catch (err) {
          set({
            autoWireStatus: "error",
            autoWireMessage:
              err instanceof Error ? err.message : "Cannot compile schematic for auto-wire.",
          });
          return;
        }
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
        set({
          nodes,
          edges,
          ...resetApprovalAndFirmware(),
          validationStatus: "idle",
          validationIssues: [],
          validationMessage: null,
          autoWireStatus: "success",
          autoWireMessage: `Added ${response.wires_added} net(s).`,
        });
      } catch (err) {
        set({
          autoWireStatus: "error",
          autoWireMessage: err instanceof Error ? err.message : "Auto-wire failed.",
        });
      }
    },
    approveSchematic: () => {
      if (get().validationStatus === "pass") {
        set({ schematicApproved: true });
      }
    },
    resetApproval: () => set({ schematicApproved: false }),
    generateFirmware: async () => {
      if (!get().schematicApproved || get().validationStatus !== "pass") {
        return;
      }
      set({ firmwareStatus: "generating", firmwareMessage: null });
      try {
        const projectState = compileProjectState(get().nodes, get().edges);
        const result = await generateFirmware(projectState, true);
        set({
          firmwareStatus: "success",
          firmwareOutputDir: result.output_dir,
          firmwareMessage: result.message,
        });
      } catch (err) {
        set({
          firmwareStatus: "error",
          firmwareMessage: err instanceof Error ? err.message : "Firmware generation failed.",
        });
      }
    },
  },
}));
