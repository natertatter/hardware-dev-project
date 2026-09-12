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

import { DEFAULT_PROJECT_ID } from "@/constants/project";
import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import {
  autoWireProjectState,
  fetchOperationsMaster,
  fetchProjectMetadata,
  fetchProjectSchematic,
  fetchManifests,
  generateFirmware,
  listProjects,
  saveProjectMetadata,
  saveProjectSchematic,
  validateProjectState,
} from "@/lib/api";
import type { CatalogEntry, HardwareNodeData, ProjectState } from "@/types/schemas";
import { useOperationsStore } from "@/store/useOperationsStore";
import { buildSchematicDraft } from "@/utils/buildSchematicDraft";
import { compileProjectState } from "@/utils/compileProjectState";
import { decompileProjectState } from "@/utils/decompileProjectState";
import { defaultProtocol, pinsForProtocol } from "@/utils/protocolProfiles";

export type ValidationStatus = "idle" | "validating" | "pass" | "fail" | "error";
export type FirmwareStatus = "idle" | "generating" | "success" | "error";
export type AutoWireStatus = "idle" | "wiring" | "success" | "error";
export type CatalogSource = "api" | "mock";
export type ProjectPersistenceStatus = "idle" | "loading" | "saving" | "error";

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
  catalogSource: CatalogSource | null;
  validationStatus: ValidationStatus;
  validationIssues: ValidationIssueView[];
  validationMessage: string | null;
  schematicApproved: boolean;
  firmwareStatus: FirmwareStatus;
  firmwareOutputDir: string | null;
  firmwareMessage: string | null;
  autoWireStatus: AutoWireStatus;
  autoWireMessage: string | null;
  projectId: string;
  projectIds: string[];
  projectStatus: ProjectPersistenceStatus;
  projectMessage: string | null;
  actions: {
    onNodesChange: (changes: NodeChange<Node<HardwareNodeData>>[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    onConnect: (connection: Connection) => void;
    addNodeFromCatalog: (entry: CatalogEntry, position?: { x: number; y: number }) => void;
    setNodeProtocol: (nodeId: string, protocol: string) => void;
    loadCatalog: () => Promise<void>;
    validateArchitecture: () => Promise<void>;
    autoWire: () => Promise<void>;
    approveSchematic: () => void;
    resetApproval: () => void;
    generateFirmware: () => Promise<void>;
    refreshProjectList: () => Promise<void>;
    loadProject: (projectId: string) => Promise<void>;
    saveProject: () => Promise<void>;
    createProject: (projectId: string) => void;
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
  useOperationsStore.getState().actions.resetOperationsApproval();
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

function mockCatalogEntries(): CatalogEntry[] {
  return COMPONENT_CATALOG.map((manifest) => ({
    label: manifest.name,
    manifest,
  }));
}

function placementOnlyProjectState(
  nodes: Node<HardwareNodeData>[],
  projectId: string,
): Pick<ProjectState, "project_id" | "nodes" | "nets"> {
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

export const useSchematicStore = create<SchematicState>((set, get) => ({
  nodes: [],
  edges: [],
  catalog: [],
  catalogLoaded: false,
  catalogError: null,
  catalogSource: null,
  validationStatus: "idle",
  validationIssues: [],
  validationMessage: null,
  schematicApproved: false,
  firmwareStatus: "idle",
  firmwareOutputDir: null,
  firmwareMessage: null,
  autoWireStatus: "idle",
  autoWireMessage: null,
  projectId: DEFAULT_PROJECT_ID,
  projectIds: [],
  projectStatus: "idle",
  projectMessage: null,
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
    addNodeFromCatalog: (entry, position) => {
      nodeCounter += 1;
      const proto = defaultProtocol(entry.manifest);
      const stackOffset = (nodeCounter - 1) % 6;
      const newNode: Node<HardwareNodeData> = {
        id: `node-${entry.manifest.component_id}-${nodeCounter}`,
        type: "hardware",
        position: position ?? {
          x: 120 + stackOffset * 48,
          y: 80 + stackOffset * 36,
        },
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
      set({ catalogLoaded: false, catalogError: null, catalogSource: null });
      try {
        const manifests = await fetchManifests();
        const catalog: CatalogEntry[] = manifests.map((manifest) => ({
          label: manifest.name,
          manifest,
        }));
        set({ catalog, catalogLoaded: true, catalogError: null, catalogSource: "api" });
      } catch (err) {
        console.warn("API catalog unavailable; using built-in parts library.", err);
        set({
          catalog: mockCatalogEntries(),
          catalogLoaded: true,
          catalogError: null,
          catalogSource: "mock",
        });
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
        const projectState = compileProjectState(get().nodes, get().edges, get().projectId);
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
        projectState = placementOnlyProjectState(currentNodes, get().projectId);
      } else {
        try {
          projectState = compileProjectState(currentNodes, currentEdges, get().projectId);
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
      if (get().validationStatus !== "pass") {
        return;
      }
      set({ schematicApproved: true });
      void (async () => {
        try {
          const metadata = await fetchProjectMetadata(get().projectId);
          await saveProjectMetadata({ ...metadata, schematic_approved: true });
        } catch {
          // Approval still applies in-session when the API is offline.
        }
      })();
    },
    resetApproval: () => set({ schematicApproved: false }),
    generateFirmware: async () => {
      if (!get().schematicApproved || get().validationStatus !== "pass") {
        return;
      }
      const opsState = useOperationsStore.getState();
      const activeOps = opsState.actions.getActiveSequence();
      if (activeOps && !opsState.operationsApproved) {
        set({
          firmwareStatus: "error",
          firmwareMessage: "Approve operations before generating firmware.",
        });
        return;
      }
      set({ firmwareStatus: "generating", firmwareMessage: null });
      try {
        const projectState = compileProjectState(get().nodes, get().edges, get().projectId);
        const result = await generateFirmware(
          projectState,
          true,
          activeOps,
          opsState.operationsApproved,
        );
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
    refreshProjectList: async () => {
      try {
        const ids = await listProjects();
        set({ projectIds: ids });
      } catch {
        set({ projectIds: [] });
      }
    },
    loadProject: async (projectId) => {
      set({ projectStatus: "loading", projectMessage: null, projectId });
      try {
        await get().actions.refreshProjectList();
        const schematic = await fetchProjectSchematic(projectId);
        const { catalog } = get();
        const manifests = Object.fromEntries(
          catalog.map((entry) => [entry.manifest.component_id, entry.manifest]),
        );
        const { nodes, edges } = decompileProjectState(schematic, manifests);
        let metadata = await fetchProjectMetadata(projectId);
        let operationsSequence = null;
        try {
          operationsSequence = await fetchOperationsMaster(projectId);
        } catch {
          operationsSequence = null;
        }
        useOperationsStore.getState().actions.hydrateFromDisk(
          operationsSequence,
          operationsSequence?.narrative ?? "",
          metadata.operations_approved,
        );
        set({
          nodes,
          edges,
          projectId,
          projectStatus: "idle",
          projectMessage: `Loaded project "${projectId}".`,
          schematicApproved: metadata.schematic_approved,
          validationStatus: "idle",
          validationIssues: [],
          validationMessage: null,
          firmwareStatus: "idle",
          firmwareOutputDir: null,
          firmwareMessage: null,
          autoWireStatus: "idle",
          autoWireMessage: null,
        });
      } catch (err) {
        set({
          projectStatus: "error",
          projectMessage:
            err instanceof Error ? err.message : `Failed to load project "${projectId}".`,
        });
      }
    },
    saveProject: async () => {
      const { nodes, edges, projectId } = get();
      set({ projectStatus: "saving", projectMessage: null });
      try {
        const draft = buildSchematicDraft(nodes, edges, projectId);
        await saveProjectSchematic(draft);
        await get().actions.refreshProjectList();
        set({
          projectStatus: "idle",
          projectMessage: `Saved projects/${projectId}/schematic.json`,
          schematicApproved: false,
        });
        const metadata = await fetchProjectMetadata(projectId);
        if (metadata.schematic_approved) {
          await saveProjectMetadata({ ...metadata, schematic_approved: false });
        }
      } catch (err) {
        set({
          projectStatus: "error",
          projectMessage: err instanceof Error ? err.message : "Save failed.",
        });
      }
    },
    createProject: (rawId) => {
      const projectId = rawId.trim().replace(/\s+/g, "_");
      if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(projectId)) {
        set({
          projectStatus: "error",
          projectMessage:
            "Project id must start with a letter and use only letters, numbers, underscores, or hyphens.",
        });
        return;
      }
      useOperationsStore.getState().actions.hydrateFromDisk(null, "", false);
      set({
        projectId,
        nodes: [],
        edges: [],
        ...resetWorkflowState(),
        validationStatus: "idle",
        validationIssues: [],
        validationMessage: null,
        projectStatus: "idle",
        projectMessage: `New project "${projectId}" — place parts and save to create files on disk.`,
      });
    },
  },
}));
