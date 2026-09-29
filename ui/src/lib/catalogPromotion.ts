import type { ExampleManifestSummary } from "@/lib/api";

/** Examples that are not yet production catalog files. */
export function unpromotedExamples(
  examples: ExampleManifestSummary[],
): ExampleManifestSummary[] {
  return examples.filter((item) => !item.promoted);
}
