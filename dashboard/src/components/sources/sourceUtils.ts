import type { Source } from "../../types";

export function formatCount(n: number, lang: string): string {
  return new Intl.NumberFormat(lang === "uk" ? "uk-UA" : "en-US").format(n);
}

export function displayStatusKey(status: string | null | undefined): string {
  const s = (status || "pending").toLowerCase();
  if (s === "ready" || s === "pending" || s === "failed" || s === "skipped" || s === "needs_refresh") {
    return s;
  }
  return "pending";
}

export function sourceTypeKey(source: Pick<Source, "source_type">): string {
  const t = (source.source_type || "").toLowerCase();
  if (t === "page" || t === "html") return "page";
  if (t === "pdf" || t === "docx" || t === "txt") return t;
  if (["pdf", "docx", "txt"].some((x) => t.includes(x))) return t;
  return "file";
}

export function formatDateTime(value: string | null | undefined, lang: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(lang === "uk" ? "uk-UA" : undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
