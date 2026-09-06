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

function validationStatusClass(status: ValidationStatus): string {
  if (status === "validating") return "editor-shell__status--pending";
  if (status === "pass") return "editor-shell__status--pass";
  if (status === "fail") return "editor-shell__status--fail";
  if (status === "error") return "editor-shell__status--error";
  return "editor-shell__status--idle";
}

function autoWireStatusClass(status: AutoWireStatus): string {
  if (status === "wiring") return "editor-shell__status--pending";
  if (status === "success") return "editor-shell__status--pass";
  if (status === "error") return "editor-shell__status--fail";
  return "editor-shell__status--idle";
}

function firmwareStatusClass(status: FirmwareStatus): string {
  if (status === "generating") return "editor-shell__status--pending";
  if (status === "success") return "editor-shell__status--pass";
  if (status === "error") return "editor-shell__status--fail";
  return "editor-shell__status--idle";
}

const STATUS_LABELS: Record<ValidationStatus, string> = {
  idle: "Not validated",
  validating: "Validating…",
  pass: "Passed",
  fail: "Failed",
  error: "Error",
};

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
  return (
    <div>
      <h2 className="editor-shell__panel-title">Validation</h2>
      <p className={`editor-shell__status ${validationStatusClass(status)}`}>
        {STATUS_LABELS[status]}
      </p>
      {message && <p className="editor-shell__note">{message}</p>}
      {schematicApproved && (
        <p className="editor-shell__banner editor-shell__banner--info">
          Schematic approved — you can generate firmware for Raspberry Pi 4.
        </p>
      )}
      {status === "fail" && issues.length > 0 && (
        <ul className="editor-shell__issue-list">
          {issues.map((issue, i) => (
            <li key={`${issue.rule}-${i}`} className="editor-shell__issue">
              <span className="editor-shell__issue-rule">{issue.rule}</span>
              <p className="editor-shell__note">{issue.message}</p>
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

      <h2 className="editor-shell__panel-title editor-shell__panel-title--spaced">Auto-Wire</h2>
      <p className={`editor-shell__status ${autoWireStatusClass(autoWireStatus)}`}>
        {autoWireStatus === "idle" && "Not run"}
        {autoWireStatus === "wiring" && "Wiring…"}
        {autoWireStatus === "success" && "Wired"}
        {autoWireStatus === "error" && "Failed"}
      </p>
      {autoWireMessage && <p className="editor-shell__note">{autoWireMessage}</p>}

      <h2 className="editor-shell__panel-title editor-shell__panel-title--spaced">
        Firmware (Pi 4)
      </h2>
      <p className={`editor-shell__status ${firmwareStatusClass(firmwareStatus)}`}>
        {firmwareStatus === "idle" && "Not generated"}
        {firmwareStatus === "generating" && "Generating…"}
        {firmwareStatus === "success" && "Generated"}
        {firmwareStatus === "error" && "Generation failed"}
      </p>
      {firmwareMessage && <p className="editor-shell__note">{firmwareMessage}</p>}
      {firmwareOutputDir && (
        <p className="editor-shell__banner editor-shell__banner--output">{firmwareOutputDir}</p>
      )}
    </div>
  );
}
