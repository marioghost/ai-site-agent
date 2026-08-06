import type { MessageStatus } from "./types";

/** Derive assistant turn status from prompt_diagnostics without inventing success. */
export function finalStatusFromPromptDiagnostics(
  promptDiagnostics: Record<string, unknown> | null | undefined,
  options?: { errorType?: string | null }
): MessageStatus {
  if (options?.errorType) return "error";
  if (promptDiagnostics && Boolean(promptDiagnostics.output_truncated)) {
    return "truncated";
  }
  return "completed";
}
