import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { useTranslation } from "../../i18n";
import type { RetrievedChunk } from "../../types";
import { StatusBadge, Tag } from "../../ui";
import { DiagnosticSection } from "./DiagnosticSection";

function SourceCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  return (
    <article className={`ds-source-card ${chunk.used_in_context ? "ds-source-card--used" : ""}`}>
      <div className="ds-source-card__head">
        <span className="ds-source-card__index">{index + 1}</span>
        <div className="ds-source-card__title-wrap">
          <h4 className="ds-source-card__title">{chunk.title || chunk.url}</h4>
          <a href={chunk.url} target="_blank" rel="noreferrer" className="ds-source-card__url">
            {chunk.url}
            <ExternalLink size={12} />
          </a>
        </div>
        <span className="ds-source-card__score">{chunk.final_score.toFixed(3)}</span>
      </div>
      <div className="ds-source-card__badges">
        <Tag>{chunk.source_type}</Tag>
        {chunk.is_canonical && <StatusBadge variant="info" label={t("trace.chunks.canonical")} size="sm" />}
        {chunk.used_in_context && (
          <StatusBadge variant="success" label={t("trace.chunks.used")} size="sm" />
        )}
        {chunk.excluded_as_news && (
          <StatusBadge variant="warning" label={t("trace.chunks.excluded_news")} size="sm" />
        )}
      </div>
      {chunk.text_preview && (
        <>
          <p className={expanded ? "ds-source-card__preview" : "ds-source-card__preview is-clamped"}>
            {chunk.text_preview}
          </p>
          <button type="button" className="ds-source-card__expand" onClick={() => setExpanded((v) => !v)}>
            {expanded ? t("sources.drawer.show_less") : t("sources.drawer.show_more")}
          </button>
        </>
      )}
    </article>
  );
}

export default function ChatRetrievedSources({ chunks }: { chunks: RetrievedChunk[] }) {
  const { t } = useTranslation();
  if (!chunks.length) return null;

  return (
    <DiagnosticSection
      title={t("trace.chunks.title", { count: chunks.length })}
      defaultOpen={false}
      badge={<span className="ds-diag-card__badge">{chunks.length}</span>}
    >
      <div className="ds-source-card-list">
        {chunks.map((chunk, i) => (
          <SourceCard key={`${chunk.url}-${i}`} chunk={chunk} index={i} />
        ))}
      </div>
    </DiagnosticSection>
  );
}
