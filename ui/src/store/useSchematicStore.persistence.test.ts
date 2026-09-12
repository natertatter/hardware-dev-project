import { beforeEach, describe, expect, it, vi } from "vitest";

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
}));

import {
  fetchProjectMetadata,
  fetchProjectSchematic,
  listProjects,
  saveProjectMetadata,
  saveProjectSchematic,
} from "@/lib/api";
import { DEFAULT_PROJECT_ID } from "@/constants/project";
import { useOperationsStore } from "@/store/useOperationsStore";
import { useSchematicStore } from "@/store/useSchematicStore";

const MCU_MANIFEST = {
  component_id: "mcu_rp2040",
  name: "MCU",
  type: "MCU",
  power_requirements: {
    min_operating_voltage: 1.8,
    max_operating_voltage: 5.5,
    logic_level_voltage: 3.3,
    max_current_draw_ma: 500,
  },
  pins: [{ pin_id: "GND", pin_type: "GND" }],
};

describe("useSchematicStore persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSchematicStore.setState({
      nodes: [],
      edges: [],
      projectId: DEFAULT_PROJECT_ID,
      projectIds: ["demo_robot"],
      projectStatus: "idle",
      projectMessage: null,
      lastSavedDraftHash: null,
      catalog: [{ label: "MCU", manifest: MCU_MANIFEST as any }],
      catalogLoaded: true,
      validationStatus: "pass",
      schematicApproved: false,
    });
    useOperationsStore.setState({
      narrative: "",
      sequence: null,
      refinedSequence: null,
      operationsApproved: false,
      operationsStatus: "idle",
    });
  });

  it("loadProject leaves projectId unchanged on fetch failure", async () => {
    (fetchProjectSchematic as any).mockRejectedValue(new Error("network"));
    await useSchematicStore.getState().actions.loadProject("other_project");
    expect(useSchematicStore.getState().projectId).toBe(DEFAULT_PROJECT_ID);
    expect(useSchematicStore.getState().projectStatus).toBe("error");
  });

  it("createProject rejects duplicate ids", () => {
    useSchematicStore.getState().actions.createProject("demo_robot");
    expect(useSchematicStore.getState().projectMessage).toMatch(/already exists/i);
  });

  it("createProject adds the new id to projectIds for the selector", () => {
    useSchematicStore.getState().actions.createProject("my_new_robot");
    expect(useSchematicStore.getState().projectId).toBe("my_new_robot");
    expect(useSchematicStore.getState().projectIds).toContain("my_new_robot");
  });

  it("approveSchematic saves before setting schematicApproved", async () => {
    const sensorManifest = {
      component_id: "sens_ina219",
      name: "Sensor",
      type: "SENSOR",
      power_requirements: MCU_MANIFEST.power_requirements,
      pins: [
        { pin_id: "GND", pin_type: "GND" },
        { pin_id: "VCC", pin_type: "POWER" },
      ],
    };
    useSchematicStore.setState({
      nodes: [
        {
          id: "mcu_1",
          type: "hardware",
          position: { x: 0, y: 0 },
          data: { manifest: MCU_MANIFEST },
        } as any,
        {
          id: "sensor_1",
          type: "hardware",
          position: { x: 0, y: 0 },
          data: { manifest: sensorManifest },
        } as any,
      ],
      edges: [
        {
          id: "e1",
          source: "mcu_1",
          sourceHandle: "GND",
          target: "sensor_1",
          targetHandle: "GND",
        },
      ],
      validationStatus: "pass",
    });
    (saveProjectSchematic as any).mockResolvedValue({ project_id: DEFAULT_PROJECT_ID, nodes: [], nets: [] });
    (fetchProjectMetadata as any).mockResolvedValue({
      project_id: DEFAULT_PROJECT_ID,
      schematic_approved: false,
      operations_approved: false,
      operations_fidelity: "narrative",
      updated_at: "2026-01-01T00:00:00+00:00",
    });
    (saveProjectMetadata as any).mockResolvedValue({});

    await useSchematicStore.getState().actions.approveSchematic();

    const saveOrder = (saveProjectSchematic as any).mock.invocationCallOrder[0];
    const metaOrder = (saveProjectMetadata as any).mock.invocationCallOrder[0];
    expect(saveOrder).toBeLessThan(metaOrder);
    expect(useSchematicStore.getState().schematicApproved).toBe(true);
  });

  it("saveProject keeps approval when draft unchanged", async () => {
    const sensorManifest = {
      component_id: "sens_ina219",
      name: "Sensor",
      type: "SENSOR",
      power_requirements: MCU_MANIFEST.power_requirements,
      pins: [
        { pin_id: "GND", pin_type: "GND" },
        { pin_id: "VCC", pin_type: "POWER" },
      ],
    };
    useSchematicStore.setState({
      nodes: [
        {
          id: "mcu_1",
          type: "hardware",
          position: { x: 0, y: 0 },
          data: { manifest: MCU_MANIFEST },
        } as any,
        {
          id: "sensor_1",
          type: "hardware",
          position: { x: 0, y: 0 },
          data: { manifest: sensorManifest },
        } as any,
      ],
      edges: [
        {
          id: "e1",
          source: "mcu_1",
          sourceHandle: "GND",
          target: "sensor_1",
          targetHandle: "GND",
        },
      ],
    });
    (saveProjectSchematic as any).mockResolvedValue({});
    (listProjects as any).mockResolvedValue([DEFAULT_PROJECT_ID]);

    await useSchematicStore.getState().actions.saveProject();
    useSchematicStore.setState({ schematicApproved: true });
    await useSchematicStore.getState().actions.saveProject();

    expect(useSchematicStore.getState().schematicApproved).toBe(true);
  });
});
