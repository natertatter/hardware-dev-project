import type { ValidationIssueView, ValidationStatus } from "@/store/useSchematicStore";

interface ValidationPanelProps {
  status: ValidationStatus;
  issues: ValidationIssueView[];
  message: string | null;
  schematicApproved: boolean;
}

const STATUS_LABELS: Record<ValidationStatus, string> = {
  idle: "Not validated",
  validating: "Validating…",
  pass: "Passed",
  fail: "Failed",
  error: "Error",
};

const STATUS_COLORS: Record<ValidationStatus, string> = {
  idle: "text-slate-400",
  validating: "text-amber-400",
  pass: "text-emerald-400",
  fail: "text-red-400",
  error: "text-orange-400",
};

export function ValidationPanel({
  status,
  issues,
  message,
  schematicApproved,
}: ValidationPanelProps) {
  return (
    <div className="space-y-3">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Validation
      </h2>
      <p className={`text-sm font-medium ${STATUS_COLORS[status]}`}>
        {STATUS_LABELS[status]}
      </p>
      {message && <p className="text-xs text-slate-400">{message}</p>}
      {schematicApproved && (
        <p className="rounded border border-blue-700 bg-blue-950/50 px-2 py-1 text-xs text-blue-300">
          Schematic approved — ready for firmware generation (Phase 9).
        </p>
      )}
      {issues.length > 0 && (
        <ul className="space-y-2">
          {issues.map((issue, i) => (
            <li
              key={`${issue.rule}-${i}`}
              className="rounded border border-red-900/60 bg-red-950/30 px-2 py-1.5 text-xs"
            >
              <span className="font-mono text-red-300">{issue.rule}</span>
              <p className="mt-0.5 text-slate-300">{issue.message}</p>
              {(issue.node_id || issue.net_id) && (
                <p className="mt-0.5 text-slate-500">
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
  );
}
