import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  saveOperationsDraft: vi.fn().mockResolvedValue({ saved_path: "projects/x/operations/drafts/draft.json" }),
  refineOperations: vi.fn(),
  validateOperations: vi.fn(),
  mergeOperations: vi.fn(),
  approveOperationsOnServer: vi.fn(),
}));

import { DEFAULT_PROJECT_ID } from "@/constants/project";
import {
  approveOperationsOnServer,
  mergeOperations,
  refineOperations,
  saveOperationsDraft,
} from "@/lib/api";
import { requiresOperationsApproval, useOperationsStore } from "@/store/useOperationsStore";
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

function placedNode(id: string) {
  return {
    id,
    type: "hardware",
    position: { x: 0, y: 0 },
    data: { manifest: MCU_MANIFEST },
  } as any;
}

describe("useOperationsStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSchematicStore.setState({ nodes: [], edges: [], projectId: DEFAULT_PROJECT_ID });
    useOperationsStore.setState({
      narrative: "",
      sequence: null,
      refinedSequence: null,
      operationsStatus: "idle",
      operationsIssues: [],
      operationsMessage: null,
      operationsApproved: false,
      refineMessage: null,
    });
  });

  describe("captureDraft", () => {
    it("succeeds for a placed-but-unwired schematic (no edges/nets)", async () => {
      // Regression: captureDraft used to call compileProjectState(), which
      // throws "no nets found" whenever nodes exist but nothing is wired
      // yet. That blocked the entire light-fidelity vibe-capture workflow
      // this feature exists for, and the throw was NOT wrapped in the
      // action's try/catch, so it propagated as an unhandled rejection
      // instead of setting a user-visible error message.
      useSchematicStore.setState({ nodes: [placedNode("mcu_1")], edges: [] });
      useOperationsStore.setState({ narrative: "Enable power rail." });

      await expect(
        useOperationsStore.getState().actions.captureDraft(),
      ).resolves.not.toThrow();

      expect(saveOperationsDraft).toHaveBeenCalledTimes(1);
      const [projectId, draft] = (saveOperationsDraft as any).mock.calls[0];
      expect(projectId).toBe(DEFAULT_PROJECT_ID);
      expect(draft.narrative).toBe("Enable power rail.");
      expect(useOperationsStore.getState().operationsMessage).toBe("Draft captured.");
    });

    it("reports a clear message instead of throwing when no nodes are placed", async () => {
      useSchematicStore.setState({ nodes: [], edges: [], projectId: DEFAULT_PROJECT_ID });
      useOperationsStore.setState({ narrative: "Enable power rail." });

      await expect(
        useOperationsStore.getState().actions.captureDraft(),
      ).resolves.not.toThrow();

      expect(saveOperationsDraft).not.toHaveBeenCalled();
      expect(useOperationsStore.getState().operationsMessage).toMatch(/place components/i);
    });

    it("does not call the API when narrative is empty", async () => {
      useSchematicStore.setState({ nodes: [placedNode("mcu_1")], edges: [] });
      useOperationsStore.setState({ narrative: "   " });

      await useOperationsStore.getState().actions.captureDraft();

      expect(saveOperationsDraft).not.toHaveBeenCalled();
      expect(useOperationsStore.getState().operationsMessage).toMatch(/enter a narrative/i);
    });
  });

  describe("setNarrative", () => {
    it("keeps a narrative-only sequence in sync with live textarea edits", () => {
      // Regression: refine() prefers `sequence` over the live `narrative`
      // state whenever a draft was captured earlier. Without syncing
      // sequence.narrative on every keystroke, edits made after "Save
      // Draft" were silently ignored by the next "Refine" click.
      useOperationsStore.setState({
        sequence: {
          project_id: "schematic_project",
          fidelity: "narrative",
          version: 1,
          narrative: "Old text.",
          steps: [],
          open_questions: [],
        },
      });

      useOperationsStore.getState().actions.setNarrative("New text.");

      expect(useOperationsStore.getState().sequence?.narrative).toBe("New text.");
    });

    it("does not overwrite a sequence that already has bound steps", () => {
      useOperationsStore.setState({
        sequence: {
          project_id: "schematic_project",
          fidelity: "steps",
          version: 2,
          narrative: null,
          steps: [{ step_id: "s1", description: "Enable power rail" }],
          open_questions: [],
        },
      });

      useOperationsStore.getState().actions.setNarrative("Unrelated new draft text.");

      const { sequence } = useOperationsStore.getState();
      expect(sequence?.steps).toHaveLength(1);
      expect(sequence?.narrative).toBeNull();
    });
  });

  describe("refine", () => {
    it("uses the live narrative when no sequence has been captured yet", async () => {
      useSchematicStore.setState({
        nodes: [placedNode("mcu_1"), placedNode("mcu_2")],
        edges: [
          {
            id: "e1",
            source: "mcu_1",
            target: "mcu_2",
            sourceHandle: "GND",
            targetHandle: "GND",
          },
        ] as any,
      });
      (refineOperations as any).mockResolvedValue({
        refined: {
          project_id: "schematic_project",
          fidelity: "steps",
          version: 1,
          steps: [],
          open_questions: [],
        },
        fidelity_promoted: true,
        previous_fidelity: "narrative",
        steps_bound: 0,
        questions_added: 0,
        warnings: [],
      });
      useOperationsStore.setState({ narrative: "Enable power rail." });

      await useOperationsStore.getState().actions.refine();

      const [inputSequence] = (refineOperations as any).mock.calls[0];
      expect(inputSequence.narrative).toBe("Enable power rail.");
    });
  });

  describe("requiresOperationsApproval", () => {
    it("returns false for narrative-only master with no steps", () => {
      expect(
        requiresOperationsApproval({
          project_id: "p",
          fidelity: "narrative",
          version: 1,
          steps: [],
          open_questions: [],
        }),
      ).toBe(false);
    });

    it("returns true when steps exist", () => {
      expect(
        requiresOperationsApproval({
          project_id: "p",
          fidelity: "narrative",
          version: 1,
          steps: [{ step_id: "s1", description: "x" }],
          open_questions: [],
        }),
      ).toBe(true);
    });
  });

  describe("approveOperations", () => {
    it("calls server approve endpoint on success", async () => {
      (approveOperationsOnServer as any).mockResolvedValue({
        project_id: DEFAULT_PROJECT_ID,
        operations_approved: true,
      });
      useOperationsStore.setState({ operationsStatus: "pass" });

      await useOperationsStore.getState().actions.approveOperations();

      expect(approveOperationsOnServer).toHaveBeenCalledWith(DEFAULT_PROJECT_ID);
      expect(useOperationsStore.getState().operationsApproved).toBe(true);
    });

    it("leaves approval false when server rejects", async () => {
      (approveOperationsOnServer as any).mockRejectedValue(new Error("422"));
      useOperationsStore.setState({ operationsStatus: "pass" });

      await useOperationsStore.getState().actions.approveOperations();

      expect(useOperationsStore.getState().operationsApproved).toBe(false);
    });

    it("does not call server approve when merge to master fails", async () => {
      (mergeOperations as any).mockRejectedValue(new Error("merge failed"));
      useOperationsStore.setState({
        operationsStatus: "pass",
        refinedSequence: {
          project_id: DEFAULT_PROJECT_ID,
          fidelity: "steps",
          version: 1,
          steps: [{ step_id: "s1", description: "x" }],
          open_questions: [],
        },
      });
      useSchematicStore.setState({
        nodes: [placedNode("mcu_1")],
        edges: [],
        projectId: DEFAULT_PROJECT_ID,
      });

      await useOperationsStore.getState().actions.approveOperations();

      expect(approveOperationsOnServer).not.toHaveBeenCalled();
      expect(useOperationsStore.getState().operationsApproved).toBe(false);
    });
  });
});
