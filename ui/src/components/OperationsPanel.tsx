import type { OperationsIssueView, OperationsStatus } from "@/store/useOperationsStore";
import { fidelityLabel } from "@/store/useOperationsStore";
import type { FidelityLevel, OperationStep } from "@/types/schemas";

interface OperationsPanelProps {
  narrative: string;
  onNarrativeChange: (text: string) => void;
  fidelity: FidelityLevel | null;
  refinedSteps: OperationStep[];
  openQuestions: { question_id: string; text: string }[];
  status: OperationsStatus;
  issues: OperationsIssueView[];
  message: string | null;
  refineMessage: string | null;
  operationsApproved: boolean;
  onCaptureDraft: () => void;
  onRefine: () => void;
  onValidate: () => void;
  onMerge: () => void;
  onApprove: () => void;
}

function statusPillClass(kind: "idle" | "pending" | "pass" | "fail" | "error"): string {
  return `status-pill status-pill--${kind}`;
}

function operationsPill(status: OperationsStatus): { className: string; label: string } {
  const labels: Record<OperationsStatus, string> = {
    idle: "Not validated",
    refining: "Refining…",
    validating: "Validating…",
    pass: "Passed",
    fail: "Failed",
    error: "Error",
  };
  const kinds: Record<OperationsStatus, "idle" | "pending" | "pass" | "fail" | "error"> = {
    idle: "idle",
    refining: "pending",
    validating: "pending",
    pass: "pass",
    fail: "fail",
    error: "error",
  };
  return { className: statusPillClass(kinds[status]), label: labels[status] };
}

export function OperationsPanel({
  narrative,
  onNarrativeChange,
  fidelity,
  refinedSteps,
  openQuestions,
  status,
  issues,
  message,
  refineMessage,
  operationsApproved,
  onCaptureDraft,
  onRefine,
  onValidate,
  onMerge,
  onApprove,
}: OperationsPanelProps) {
  const pill = operationsPill(status);

  return (
    <div className="panel-card operations-panel">
      <div className="panel-card__header">
        <h2 className="panel-card__title">Operations</h2>
        <span className={pill.className}>{pill.label}</span>
      </div>

      {fidelity && (
        <p className="operations-panel__fidelity">
          Fidelity: <strong>{fidelityLabel(fidelity)}</strong>
        </p>
      )}

      <label className="operations-panel__label" htmlFor="ops-narrative">
        Sequence (vibe input)
      </label>
      <textarea
        id="ops-narrative"
        className="operations-panel__textarea"
        rows={5}
        placeholder="Describe how the system should operate…&#10;e.g. Enable power, wait 100ms, poll sensor_1 current."
        value={narrative}
        onChange={(e) => onNarrativeChange(e.target.value)}
      />

      <div className="operations-panel__actions">
        <button type="button" className="editor-shell__btn" onClick={onCaptureDraft}>
          Save Draft
        </button>
        <button
          type="button"
          className="editor-shell__btn"
          onClick={onRefine}
          disabled={status === "refining"}
        >
          {status === "refining" ? "Refining…" : "Refine"}
        </button>
        <button
          type="button"
          className="editor-shell__btn editor-shell__btn--validate"
          onClick={onValidate}
          disabled={status === "validating" || status === "refining"}
        >
          {status === "validating" ? "Validating…" : "Validate"}
        </button>
        <button type="button" className="editor-shell__btn" onClick={onMerge}>
          Merge
        </button>
        <button
          type="button"
          className="editor-shell__btn editor-shell__btn--approve"
          onClick={onApprove}
          disabled={status !== "pass" || operationsApproved}
        >
          {operationsApproved ? "Approved" : "Approve Ops"}
        </button>
      </div>

      {refineMessage && <p className="panel-card__message">{refineMessage}</p>}
      {message && <p className="panel-card__message">{message}</p>}

      {operationsApproved && (
        <p className="editor-shell__banner editor-shell__banner--verified">
          Operations approved — included in firmware generation.
        </p>
      )}

      {refinedSteps.length > 0 && (
        <div className="operations-panel__steps">
          <h3 className="operations-panel__subtitle">Refined steps</h3>
          <ol className="operations-panel__step-list">
            {refinedSteps.map((step) => (
              <li key={step.step_id} className="operations-panel__step">
                <span>{step.description}</span>
                {step.target_node_id && (
                  <span className="operations-panel__meta"> → {step.target_node_id}</span>
                )}
                {step.timing?.delay_ms != null && (
                  <span className="operations-panel__meta"> ({step.timing.delay_ms} ms)</span>
                )}
                {step.timing?.period_ms != null && (
                  <span className="operations-panel__meta">
                    {" "}
                    every {step.timing.period_ms} ms
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {openQuestions.length > 0 && (
        <div className="operations-panel__questions">
          <h3 className="operations-panel__subtitle">Open questions</h3>
          <ul className="editor-shell__issue-list">
            {openQuestions.map((q) => (
              <li key={q.question_id} className="editor-shell__issue">
                <p className="panel-card__message">{q.text}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === "fail" && issues.length > 0 && (
        <ul className="editor-shell__issue-list">
          {issues.map((issue, i) => (
            <li key={`${issue.rule}-${i}`} className="editor-shell__issue">
              <span className="editor-shell__issue-rule">{issue.rule}</span>
              <p className="panel-card__message">{issue.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
