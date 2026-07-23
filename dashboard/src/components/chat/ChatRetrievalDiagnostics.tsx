import { Button } from "../../ui";
import { useTranslation } from "../../i18n";
import { DiagnosticSection, KvGrid, asList } from "./DiagnosticSection";

type RetrievalDebug = Record<string, unknown>;

function cacheRecord(debug: RetrievalDebug): Record<string, unknown> {
  const nested = debug.cache;
  if (nested && typeof nested === "object") {
    return nested as Record<string, unknown>;
  }
  return debug;
}

export default function ChatRetrievalDiagnostics({
  debug,
  lastUserMessage,
  onRetryWithoutCache,
}: {
  debug: RetrievalDebug | null | undefined;
  lastUserMessage?: string;
  onRetryWithoutCache?: (message: string) => void;
}) {
  const { t, cacheTypeLabel } = useTranslation();
  if (!debug || Object.keys(debug).length === 0) return null;

  const intent = debug.intent ?? debug.legacy_intent;
  const expanded = debug.expanded_queries ?? debug.expanded_terms ?? debug.variants;
  const cache = cacheRecord(debug);
  const cacheType = String(cache.cache_type ?? debug.cache_type ?? "none");
  const showEmptyCacheWarning =
    Boolean(cache.negative_cache) ||
    (Boolean(cache.retrieval_cache_hit) &&
      Number(cache.cached_selected_chunk_count ?? 0) === 0 &&
      cache.cached_context_used === false);

  const candidates = debug.candidate_pages ?? debug.final;
  const reranked = debug.reranked_pages;

  return (
    <DiagnosticSection title={t("trace.retrieval_diag.title")} defaultOpen={false}>
      <KvGrid
        items={[
          { label: t("trace.retrieval_diag.cache_type"), value: cacheTypeLabel(cacheType) },
          { label: t("trace.retrieval_diag.cache_key"), value: asList(cache.cache_key), mono: true },
          {
            label: t("trace.retrieval_diag.cache_age"),
            value: typeof cache.cache_age_seconds === "number" ? cache.cache_age_seconds : "—",
          },
          {
            label: t("trace.retrieval_diag.cache_ttl"),
            value: typeof cache.cache_ttl_seconds === "number" ? cache.cache_ttl_seconds : "—",
          },
          {
            label: t("trace.retrieval_diag.cache_chunks"),
            value:
              typeof cache.cached_selected_chunk_count === "number"
                ? cache.cached_selected_chunk_count
                : "—",
          },
          {
            label: t("trace.retrieval_diag.cache_context"),
            value: cache.cached_context_used ? t("common.yes") : t("common.no"),
          },
          {
            label: t("trace.retrieval_diag.cache_negative"),
            value: cache.negative_cache ? t("common.yes") : t("common.no"),
          },
          { label: t("trace.retrieval_diag.intent"), value: asList(intent) },
          {
            label: t("trace.retrieval_diag.topic"),
            value: asList(debug.matched_topic_label ?? debug.matched_topic_key),
          },
          { label: t("trace.retrieval_diag.aliases"), value: asList(debug.matched_aliases) },
          { label: t("trace.retrieval_diag.patterns"), value: asList(debug.matched_patterns) },
          { label: t("trace.retrieval_diag.strategy"), value: asList(debug.answer_strategy) },
          { label: t("trace.retrieval_diag.expanded"), value: asList(expanded) },
          { label: t("trace.retrieval_diag.boosts"), value: asList(debug.category_boosts_applied) },
          {
            label: t("trace.retrieval_diag.boost_doc_types"),
            value: asList(debug.boost_document_types),
          },
          {
            label: t("trace.retrieval_diag.boost_hints"),
            value: asList(debug.boost_content_hints),
          },
          { label: t("trace.retrieval_diag.injected"), value: asList(debug.broad_injected) },
          {
            label: t("trace.retrieval_diag.candidates"),
            value: typeof debug.candidate_count === "number" ? debug.candidate_count : "—",
          },
          {
            label: t("trace.retrieval_diag.chunks"),
            value: typeof debug.final_chunk_count === "number" ? debug.final_chunk_count : "—",
          },
          {
            label: t("trace.retrieval_diag.context_len"),
            value: typeof debug.context_length === "number" ? debug.context_length : "—",
          },
          {
            label: t("trace.retrieval_diag.prompt_len"),
            value: typeof debug.prompt_length === "number" ? debug.prompt_length : "—",
          },
          { label: "Profile routing", value: asList(debug.source_profile_routing) },
          { label: "Query language", value: asList(debug.query_language) },
          ...(debug.error_type
            ? [{ label: "Error type", value: String(debug.error_type) }]
            : []),
          ...(debug.no_answer_reason
            ? [{ label: t("trace.retrieval_diag.no_answer"), value: String(debug.no_answer_reason) }]
            : []),
        ]}
      />

      {showEmptyCacheWarning && (
        <p className="ds-alert ds-alert--warning" style={{ marginTop: 12 }}>
          {t("trace.retrieval_diag.cache_warning")}
        </p>
      )}

      {lastUserMessage && onRetryWithoutCache && (
        <div style={{ marginTop: 12 }}>
          <Button type="button" variant="secondary" size="sm" onClick={() => onRetryWithoutCache(lastUserMessage)}>
            {t("trace.retrieval_diag.retry_no_cache")}
          </Button>
        </div>
      )}

      {typeof debug.context_preview === "string" && debug.context_preview.length > 0 && (
        <div className="ds-diag-subsection">
          <h4 className="ds-diag-subsection__title">Context preview</h4>
          <pre className="ds-code-block" style={{ maxHeight: 200, overflow: "auto" }}>
            {debug.context_preview}
          </pre>
        </div>
      )}

      {Array.isArray(candidates) && candidates.length > 0 && (
        <div className="ds-diag-subsection">
          <h4 className="ds-diag-subsection__title">{t("trace.retrieval_diag.before_rerank")}</h4>
          <ul className="ds-preview-list">
            {(candidates as Array<Record<string, unknown>>).slice(0, 8).map((p) => (
              <li key={`c-${String(p.url || p.title)}`}>
                <strong>{String(p.title || p.url)}</strong>
                {p.document_type ? ` [${String(p.document_type)}]` : ""}
                {typeof p.final_score === "number" ? ` — ${p.final_score.toFixed(2)}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(reranked) && reranked.length > 0 && (
        <div className="ds-diag-subsection">
          <h4 className="ds-diag-subsection__title">{t("trace.retrieval_diag.after_rerank")}</h4>
          <ul className="ds-preview-list">
            {(reranked as Array<{ title?: string; url?: string; score?: number; category?: string }>)
              .slice(0, 8)
              .map((p) => (
                <li key={p.url || p.title}>
                  {p.title || p.url} ({p.category}) — {p.score?.toFixed?.(2) ?? p.score}
                </li>
              ))}
          </ul>
        </div>
      )}
    </DiagnosticSection>
  );
}
