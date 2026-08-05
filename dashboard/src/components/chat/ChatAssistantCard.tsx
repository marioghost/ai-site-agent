import { useState } from "react";
import { Copy, Check, Sparkles } from "lucide-react";
import { useTranslation } from "../../i18n";
import type { ChatSource, RequestMetadata, TimingMetrics } from "../../types";
import type { MessageStatus } from "../../chat/types";
import { StatusBadge, Tag } from "../../ui";
import { MetricPills } from "./DiagnosticSection";

type Props = {
  text: string;
  sources?: ChatSource[];
  sourcesStatus?: "loading" | "ready" | "empty";
  usedContext?: boolean;
  cacheHit?: boolean;
  cacheType?: string;
  timing?: TimingMetrics | Partial<TimingMetrics>;
  metadata?: RequestMetadata | null;
  model?: string;
  streaming?: boolean;
  status?: MessageStatus;
  selected?: boolean;
  selectable?: boolean;
  onSelect?: () => void;
  /** Product Ask hides engineering diagnostics; Engineering surfaces keep them. */
  density?: "product" | "engineering";
};

function useFormatMs() {
  const { t, lang } = useTranslation();
  return (ms: number): string => {
    if (ms >= 1000) return t("common.seconds", { value: (ms / 1000).toFixed(2) });
    return lang === "uk" ? `${ms} мс` : t("common.ms", { value: ms });
  };
}

export default function ChatAssistantCard({
  text,
  sources,
  sourcesStatus,
  usedContext,
  cacheHit,
  cacheType,
  timing,
  metadata,
  model,
  streaming = false,
  status,
  selected = false,
  selectable = false,
  onSelect,
  density = "engineering",
}: Props) {
  const { t, cacheTypeLabel } = useTranslation();
  const formatMs = useFormatMs();
  const [copied, setCopied] = useState(false);
  const product = density === "product";

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  const metrics =
    !product && (timing || usedContext !== undefined || cacheHit !== undefined)
      ? [
          {
            label: t("chat.used_context"),
            value: usedContext ? t("common.yes") : t("common.no"),
          },
          {
            label: t("chat.cache_hit"),
            value: cacheHit ? t("common.yes") : t("common.no"),
          },
          ...(cacheType && cacheType !== "none"
            ? [{ label: t("chat.cache_type"), value: cacheTypeLabel(cacheType) }]
            : []),
          ...(timing?.total_ms != null
            ? [{ label: t("chat.response_time"), value: formatMs(timing.total_ms) }]
            : streaming
              ? [{ label: t("chat.response_time"), value: t("chat.metric_waiting") }]
              : []),
          ...(timing?.retrieval_ms != null
            ? [{ label: t("chat.search_time"), value: formatMs(timing.retrieval_ms) }]
            : []),
          ...(timing?.generation_ms != null
            ? [{ label: t("chat.llm_time"), value: formatMs(timing.generation_ms) }]
            : streaming
              ? [{ label: t("chat.llm_time"), value: t("chat.metric_waiting") }]
              : []),
          ...(sources?.length
            ? [{ label: t("chat.sources_count"), value: String(sources.length) }]
            : []),
          ...(model ? [{ label: t("chat.model"), value: model }] : []),
        ]
      : [];

  const showSources =
    sourcesStatus === "loading" ||
    sourcesStatus === "ready" ||
    sourcesStatus === "empty" ||
    (sources && sources.length > 0);

  return (
    <article className="ds-chat-assistant">
      <div
        className={[
          "ds-chat-assistant__card",
          selectable ? "ds-chat-assistant__card--selectable" : "",
          selected ? "ds-chat-assistant__card--selected" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        role={selectable ? "button" : undefined}
        tabIndex={selectable ? 0 : undefined}
        onClick={selectable ? onSelect : undefined}
        onKeyDown={
          selectable
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect?.();
                }
              }
            : undefined
        }
      >
        <header className="ds-chat-assistant__header">
          <span className="ds-chat-assistant__brand">
            <Sparkles size={16} aria-hidden />
            {t("chat.answer")}
          </span>
          {(streaming || status === "streaming") && (
            <span className="ds-chat-assistant__thinking-badge">{t("chat.thinking")}</span>
          )}
          <div className="ds-chat-assistant__actions">
            <button
              type="button"
              className="ds-chat-user__copy"
              onClick={(event) => {
                event.stopPropagation();
                void onCopy();
              }}
              aria-label={t("chat.copy")}
            >
              {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
            </button>
          </div>
        </header>

        <div className="ds-chat-assistant__body">
          {text ? (
            text
          ) : streaming ? (
            <div className="ds-chat-assistant__thinking">
              <span className="ds-chat-assistant__thinking-dots" aria-hidden>
                <span />
                <span />
                <span />
              </span>
              <span>{t("chat.thinking")}</span>
            </div>
          ) : null}
        </div>

        {(streaming || status === "streaming") && text && (
          <p className="ds-chat-assistant__streaming-label">{t("chat.streaming")}</p>
        )}

        {showSources && (
          <section className="ds-chat-assistant__section" aria-label={t("chat.sources")}>
            <div className="ds-chat-assistant__section-title">{t("chat.sources")}</div>
            {sourcesStatus === "loading" || (streaming && !sources?.length) ? (
              <p className="ds-chat-assistant__source-loading">{t("chat.sources_loading")}</p>
            ) : sources && sources.length > 0 ? (
              <div className="ds-chat-assistant__sources">
                {sources.map((s, i) => (
                  <div key={`${s.url}-${i}`} className="ds-chat-assistant__source">
                    <a href={s.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                      {s.title || s.url}
                    </a>
                    {!product && (
                      <span className="ds-chat-assistant__source-meta">
                        {s.source_type} · {s.score.toFixed(3)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="ds-chat-assistant__source-loading">{t("chat.sources_none")}</p>
            )}
            {product && !streaming && sourcesStatus === "empty" && (
              <p className="ds-chat-assistant__trust">{t("chat.sources_none_hint")}</p>
            )}
          </section>
        )}

        {metrics.length > 0 && (
          <section className="ds-chat-assistant__section" aria-label={t("chat.metrics")}>
            <div className="ds-chat-assistant__section-title">{t("chat.metrics")}</div>
            <MetricPills items={metrics} />
          </section>
        )}

        {!product && metadata && (metadata.query_intent || metadata.retrieval_mode) && (
          <section className="ds-chat-assistant__section" aria-label={t("chat.intent_mode")}>
            <div className="ds-chat-assistant__section-title">{t("chat.intent_mode")}</div>
            <div className="ds-chat-assistant__badges">
              {metadata.query_intent && (
                <StatusBadge variant="info" label={t(`intent.${metadata.query_intent}`)} size="sm" />
              )}
              {metadata.retrieval_mode && <Tag>{metadata.retrieval_mode}</Tag>}
            </div>
          </section>
        )}
      </div>
    </article>
  );
}
