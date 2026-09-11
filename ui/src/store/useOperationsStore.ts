import { create } from "zustand";

import {
  mergeOperations,
  refineOperations,
  saveOperationsDraft,
  validateOperations,
} from "@/lib/api";
import type { FidelityLevel, OperationsSequence } from "@/types/schemas";
import { compileProjectState } from "@/utils/compileProjectState";
import { useSchematicStore } from "@/store/useSchematicStore";

export type OperationsStatus = "idle" | "refining" | "validating" | "pass" | "fail" | "error";

export interface OperationsIssueView {
  rule: string;
  severity: string;
  message: string;
  step_id?: string;
}

const DEFAULT_PROJECT_ID = "schematic_project";

function emptySequence(projectId: string): OperationsSequence {
  return {
    project_id: projectId,
    fidelity: "narrative",
    version: 1,
    narrative: "",
    steps: [],
    open_questions: [],
  };
}

interface OperationsState {
  narrative: string;
  sequence: OperationsSequence | null;
  refinedSequence: OperationsSequence | null;
  operationsStatus: OperationsStatus;
  operationsIssues: OperationsIssueView[];
  operationsMessage: string | null;
  operationsApproved: boolean;
  refineMessage: string | null;
  actions: {
    setNarrative: (text: string) => void;
    captureDraft: () => Promise<void>;
    refine: () => Promise<void>;
    validate: () => Promise<void>;
    mergeToMaster: () => Promise<void>;
    approveOperations: () => void;
    resetOperationsApproval: () => void;
    getActiveSequence: () => OperationsSequence | null;
  };
}

function schematicProjectState() {
  const { nodes, edges } = useSchematicStore.getState();
  if (nodes.length === 0) {
    throw new Error("Place components on the schematic before working with operations.");
  }
  return compileProjectState(nodes, edges);
}

export const useOperationsStore = create<OperationsState>((set, get) => ({
  narrative: "",
  sequence: null,
  refinedSequence: null,
  operationsStatus: "idle",
  operationsIssues: [],
  operationsMessage: null,
  operationsApproved: false,
  refineMessage: null,
  actions: {
    setNarrative: (text) => {
      // Keep a still-narrative-only sequence (captured via a prior "Save
      // Draft") in sync with live edits. Without this, refine() prefers
      // `sequence` over the freshly typed `narrative` whenever a draft was
      // saved earlier, so edits made after that point are silently dropped
      // on the next Refine click. A sequence that has already progressed to
      // bound steps (post-refine/merge) is left alone — the user is editing
      // step-level data at that point, not narrative text.
      const current = get().sequence;
      const syncedSequence =
        current && current.steps.length === 0 ? { ...current, narrative: text } : current;
      set({
        narrative: text,
        sequence: syncedSequence,
        operationsApproved: false,
        refinedSequence: null,
        operationsStatus: "idle",
        operationsIssues: [],
        operationsMessage: null,
      });
    },
    captureDraft: async () => {
      const narrative = get().narrative.trim();
      if (!narrative) {
        set({ operationsMessage: "Enter a narrative description first." });
        return;
      }
      try {
        const { nodes } = useSchematicStore.getState();
        if (nodes.length === 0) {
          set({
            operationsMessage: "Place components on the schematic before capturing a draft.",
          });
          return;
        }
        // A draft capture is a lightweight vibe/narrative note — it must not
        // require a fully wired schematic. Deriving the project id via
        // compileProjectState() would throw "no nets found" for a
        // placement-only canvas, blocking the exact light-fidelity, early
        // capture workflow this feature exists for. The project id is a
        // fixed constant across the single-project UI, so use it directly.
        const draft: OperationsSequence = {
          ...emptySequence(DEFAULT_PROJECT_ID),
          narrative,
        };
        await saveOperationsDraft(DEFAULT_PROJECT_ID, draft);
        set({
          sequence: draft,
          operationsMessage: "Draft captured.",
          operationsApproved: false,
        });
      } catch (err) {
        set({
          operationsMessage: err instanceof Error ? err.message : "Failed to save draft.",
        });
      }
    },
    refine: async () => {
      set({
        operationsStatus: "refining",
        operationsMessage: null,
        refineMessage: null,
        operationsIssues: [],
      });
      try {
        const projectState = schematicProjectState();
        const narrative = get().narrative.trim();
        const input: OperationsSequence =
          get().sequence ??
          ({
            ...emptySequence(projectState.project_id),
            narrative,
          } as OperationsSequence);

        if (!input.narrative && input.steps.length === 0) {
          set({
            operationsStatus: "error",
            operationsMessage: "Enter narrative text or steps before refining.",
          });
          return;
        }

        const result = await refineOperations(input, projectState);
        set({
          refinedSequence: result.refined,
          operationsStatus: "idle",
          refineMessage: `Refined ${result.steps_bound} step(s); fidelity ${result.previous_fidelity} → ${result.refined.fidelity}`,
          operationsApproved: false,
        });
      } catch (err) {
        set({
          operationsStatus: "error",
          operationsMessage: err instanceof Error ? err.message : "Refine failed.",
        });
      }
    },
    validate: async () => {
      set({
        operationsStatus: "validating",
        operationsMessage: null,
        operationsIssues: [],
      });
      try {
        const projectState = schematicProjectState();
        const sequence = get().refinedSequence ?? get().sequence;
        if (!sequence) {
          set({
            operationsStatus: "error",
            operationsMessage: "Refine or capture a draft before validating.",
          });
          return;
        }
        const result = await validateOperations(sequence, projectState);
        if (result.valid) {
          set({
            operationsStatus: "pass",
            operationsIssues: [],
            operationsMessage: "Operations passed validation.",
          });
        } else {
          set({
            operationsStatus: "fail",
            operationsIssues: result.errors.map((e) => ({
              rule: e.rule,
              severity: e.severity,
              message: e.message,
              step_id: e.step_id ?? undefined,
            })),
            operationsMessage: `${result.errors.length} issue(s) found.`,
          });
        }
      } catch (err) {
        set({
          operationsStatus: "error",
          operationsMessage: err instanceof Error ? err.message : "Validation failed.",
        });
      }
    },
    mergeToMaster: async () => {
      const sequence = get().refinedSequence;
      if (!sequence) {
        set({ operationsMessage: "Refine operations before merging to master." });
        return;
      }
      try {
        const projectState = schematicProjectState();
        const result = await mergeOperations(sequence, projectState);
        set({
          sequence: result.master,
          refinedSequence: result.master,
          operationsMessage: result.message,
        });
      } catch (err) {
        set({
          operationsMessage: err instanceof Error ? err.message : "Merge failed.",
        });
      }
    },
    approveOperations: () => {
      if (get().operationsStatus === "pass") {
        set({ operationsApproved: true });
      }
    },
    resetOperationsApproval: () => set({ operationsApproved: false }),
    getActiveSequence: () => get().refinedSequence ?? get().sequence,
  },
}));

export function fidelityLabel(level: FidelityLevel): string {
  const labels: Record<FidelityLevel, string> = {
    narrative: "Narrative",
    steps: "Steps",
    timed: "Timed",
    executable: "Executable",
  };
  return labels[level];
}
