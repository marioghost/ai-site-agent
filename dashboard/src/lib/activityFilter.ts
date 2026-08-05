import type { ChatLog } from "../types";

/** Client-side filter over the currently loaded Activity page only. */
export function filterActivityPage(logs: ChatLog[], query: string): ChatLog[] {
  const q = query.trim().toLowerCase();
  if (!q) return logs;
  return logs.filter((log) => {
    const hay = `${log.user_message} ${log.assistant_answer}`.toLowerCase();
    return hay.includes(q);
  });
}
