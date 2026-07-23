import type { IntentDistributionRow } from "../types";

export type IntentDistributionDisplayRow = {
  key: string;
  label: string;
  count: number;
  share: number;
};

/** Top intents for compact charts; remaining intents grouped as "other". */
export function topIntentRows(
  rows: IntentDistributionRow[],
  labelFor: (intent: string) => string,
  limit = 5
): IntentDistributionDisplayRow[] {
  if (!rows.length) return [];

  const sorted = [...rows].sort((a, b) => b.count - a.count);
  const total = sorted.reduce((sum, row) => sum + row.count, 0) || 1;
  const top = sorted.slice(0, limit);
  const rest = sorted.slice(limit);

  const result: IntentDistributionDisplayRow[] = top.map((row) => ({
    key: row.intent,
    label: labelFor(row.intent),
    count: row.count,
    share: row.count / total,
  }));

  if (rest.length) {
    const count = rest.reduce((sum, row) => sum + row.count, 0);
    result.push({
      key: "__other__",
      label: labelFor("other"),
      count,
      share: count / total,
    });
  }

  return result;
}
