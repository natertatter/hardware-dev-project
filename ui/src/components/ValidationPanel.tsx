import type {
  AutoWireStatus,
  FirmwareStatus,
  ValidationIssueView,
  ValidationStatus,
} from "@/store/useSchematicStore";

interface ValidationPanelProps {
  status: ValidationStatus;
  issues: ValidationIssueView[];
  message: string | null;
  schematicApproved: boolean;
  autoWireStatus: AutoWireStatus;
  autoWireMessage: string | null;
  firmwareStatus: FirmwareStatus;
  firmwareOutputDir: string | null;
  firmwareMessage: string | null;
}

function statusPillClass(kind: "idle" | "pending" | "pass" | "fail" | "error"): string {
  return `status-pill status-pill--${kind}`;
}

function validationPill(status: ValidationStatus): { className: string; label: string } {
  const labels: Record<ValidationStatus, string> = {
    idle: "Not validated",
    validating: "Validating…",
    pass: "Passed",
    fail: "Failed",
    error: "Error",
  };
  const kinds: Record<ValidationStatus, "idle" | "pending" | "pass" | "fail" | "error"> = {
    idle: "idle",
    validating: "pending",
    pass: "pass",
    fail: "fail",
    error: "error",
  };
  return { className: statusPillClass(kinds[status]), label: labels[status] };
}

function autoWirePill(status: AutoWireStatus): { className: string; label: string } {
  const labels: Record<AutoWireStatus, string> = {
    idle: "Not run",
    wiring: "Wiring…",
    success: "Wired",
    error: "Failed",
  };
  const kinds: Record<AutoWireStatus, "idle" | "pending" | "pass" | "fail"> = {
    idle: "idle",
    wiring: "pending",
    success: "pass",
    error: "fail",
  };
  return { className: statusPillClass(kinds[status]), label: labels[status] };
}

function firmwarePill(status: FirmwareStatus): { className: string; label: string } {
  const labels: Record<FirmwareStatus, string> = {
    idle: "Not generated",
    generating: "Generating…",
    success: "Generated",
    error: "Failed",
  };
  const kinds: Record<FirmwareStatus, "idle" | "pending" | "pass" | "fail"> = {
    idle: "idle",
    generating: "pending",
    success: "pass",
    error: "fail",
  };
  return { className: statusPillClass(kinds[status]), label: labels[status] };
}

export function ValidationPanel({
  status,
  issues,
  message,
  schematicApproved,
  autoWireStatus,
  autoWireMessage,
  firmwareStatus,
  firmwareOutputDir,
  firmwareMessage,
}: ValidationPanelProps) {
  const validation = validationPill(status);
  const autoWire = autoWirePill(autoWireStatus);
  const firmware = firmwarePill(firmwareStatus);

  return (
    <>
      <div className="panel-card">
        <div className="panel-card__header">
          <h2 className="panel-card__title">Validation</h2>
          <span className={validation.className}>{validation.label}</span>
        </div>
        {message && <p className="panel-card__message">{message}</p>}
        {schematicApproved && (
          <p className="editor-shell__banner editor-shell__banner--verified">
            Schematic approved — ready to generate Pi 4 firmware.
          </p>
        )}
        {status === "fail" && issues.length > 0 && (
          <ul className="editor-shell__issue-list">
            {issues.map((issue, i) => (
              <li key={`${issue.rule}-${i}`} className="editor-shell__issue">
                <span className="editor-shell__issue-rule">{issue.rule}</span>
                <p className="panel-card__message">{issue.message}</p>
                {(issue.node_id || issue.net_id) && (
                  <p className="editor-shell__issue-meta">
                    {issue.node_id && `node: ${issue.node_id}`}
                    {issue.node_id && issue.net_id && " · "}
                    {issue.net_id && `net: ${issue.net_id}`}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="panel-card">
        <div className="panel-card__header">
          <h2 className="panel-card__title">Auto-Wire</h2>
          <span className={autoWire.className}>{autoWire.label}</span>
        </div>
        {autoWireMessage && <p className="panel-card__message">{autoWireMessage}</p>}
      </div>

      <div className="panel-card">
        <div className="panel-card__header">
          <h2 className="panel-card__title">Firmware</h2>
          <span className={firmware.className}>{firmware.label}</span>
        </div>
        {firmwareMessage && <p className="panel-card__message">{firmwareMessage}</p>}
        {firmwareOutputDir && (
          <p className="editor-shell__banner editor-shell__banner--output">{firmwareOutputDir}</p>
        )}
      </div>
    </>
  );
}
