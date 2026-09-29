import type { TimingConstraint } from "@/types/schemas";

const SOURCE_LABEL: Record<string, string> = {
  human: "human",
  datasheet: "datasheet",
  best_practice: "best practice",
  inferred: "inferred",
};

/** Compact label for a refined step's delay or period and where it came from. */
export function formatStepTiming(timing: TimingConstraint): string {
  const parts: string[] = [];
  if (timing.delay_ms != null) parts.push(`${timing.delay_ms} ms`);
  if (timing.period_ms != null) parts.push(`every ${timing.period_ms} ms`);
  if (timing.source) parts.push(SOURCE_LABEL[timing.source] ?? timing.source);
  return parts.join(" · ");
}
