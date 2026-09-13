import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/utils/compileProjectState", () => ({
  compileProjectState: vi.fn(() => ({
    project_id: "demo_robot",
    nodes: [{ node_id: "n1", component_id: "mcu_rp2040" }],
    nets: [],
  })),
}));

vi.mock("@/lib/api", () => ({
  fetchManifests: vi.fn(),
  listProjects: vi.fn(),
  fetchProjectSchematic: vi.fn(),
  fetchProjectMetadata: vi.fn(),
  fetchOperationsMaster: vi.fn(),
  saveProjectSchematic: vi.fn(),
  saveProjectMetadata: vi.fn(),
  validateProjectState: vi.fn(),
  autoWireProjectState: vi.fn(),
  generateFirmware: vi.fn(),
  generateOperatingDocs: vi.fn(),
}));

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import { generateFirmware, generateOperatingDocs } from "@/lib/api";
import { useOperationsStore } from "@/store/useOperationsStore";
import { useSchematicStore } from "@/store/useSchematicStore";

describe("useSchematicStore operating docs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSchematicStore.getState().actions.addNodeFromCatalog({
      label: "MCU",
      manifest: COMPONENT_CATALOG[0],
    });
    useSchematicStore.setState({
      schematicApproved: true,
      validationStatus: "pass",
      firmwareStatus: "idle",
      firmwareOutputDir: null,
      firmwareMessage: null,
      operatingProcedureMd: null,
      bringupChecklistMd: null,
      operatingDocsMessage: null,
      projectId: "demo_robot",
    });
    useOperationsStore.setState({
      narrative: "",
      sequence: null,
      refinedSequence: null,
      operationsApproved: true,
    });
  });

  it("populates doc previews after successful firmware generate", async () => {
    vi.mocked(generateFirmware).mockResolvedValue({
      success: true,
      project_id: "demo_robot",
      output_dir: "generated/firmware/demo_robot",
      files_written: [],
      message: "ok",
    });
    vi.mocked(generateOperatingDocs).mockResolvedValue({
      operating_procedure: "# Procedure",
      bringup_checklist: "- [ ] Power",
    });
    useOperationsStore.setState({
      sequence: {
        project_id: "demo_robot",
        fidelity: "timed",
        version: 1,
        steps: [],
      } as any,
      operationsApproved: true,
    });

    await useSchematicStore.getState().actions.generateFirmware();

    const state = useSchematicStore.getState();
    expect(state.firmwareStatus).toBe("success");
    expect(state.operatingProcedureMd).toBe("# Procedure");
    expect(state.bringupChecklistMd).toBe("- [ ] Power");
    expect(state.operatingDocsMessage).toBeNull();
  });

  it("surfaces docs fetch failure without failing firmware success", async () => {
    vi.mocked(generateFirmware).mockResolvedValue({
      success: true,
      project_id: "demo_robot",
      output_dir: "out",
      files_written: [],
      message: "ok",
    });
    vi.mocked(generateOperatingDocs).mockRejectedValue(new Error("503 unavailable"));
    useOperationsStore.setState({
      sequence: {
        project_id: "demo_robot",
        fidelity: "timed",
        version: 1,
        steps: [],
      } as any,
      operationsApproved: true,
    });

    await useSchematicStore.getState().actions.generateFirmware();

    const state = useSchematicStore.getState();
    expect(state.firmwareStatus).toBe("success");
    expect(state.operatingProcedureMd).toBeNull();
    expect(state.operatingDocsMessage).toMatch(/Operating docs unavailable/i);
  });

  it("clears doc previews when the canvas changes", () => {
    useSchematicStore.setState({
      operatingProcedureMd: "# stale",
      bringupChecklistMd: "- stale",
      schematicApproved: true,
    });

    useSchematicStore.getState().actions.onNodesChange([
      { id: "n1", type: "remove" } as any,
    ]);

    const state = useSchematicStore.getState();
    expect(state.operatingProcedureMd).toBeNull();
    expect(state.bringupChecklistMd).toBeNull();
  });
});
