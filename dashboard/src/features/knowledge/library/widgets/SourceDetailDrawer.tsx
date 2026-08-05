import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import type { SourceDetail } from "../../../../types";
import SourceIntelligencePanel from "./SourceIntelligencePanel";
import { Button, Drawer, LoadingState, StatusBadge, type StatusVariant } from "../../../../ui";
import { displayStatusKey, formatDateTime, sourceTypeKey } from "./sourceUtils";

type Props = {
  detail: SourceDetail | null;
  loading?: boolean;
  lang: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
  busy?: boolean;
  onClose: () => void;
  onReindex: (id: number) => void;
  onDelete: (id: number) => void;
};

export default function SourceDetailDrawer({
  detail,
  loading = false,
  lang,
  t,
  busy = false,
  onClose,
  onReindex,
  onDelete,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setExpanded(false);
  }, [detail?.id]);

  const statusKey = displayStatusKey(detail?.display_status);
  const variantMap: Record<string, StatusVariant> = {
    ready: "ready",
    pending: "pending",
    failed: "failed",
    skipped: "skipped",
    needs_refresh: "needs_refresh",
  };
  const badgeVariant = variantMap[statusKey] ?? "pending";
  const badgeLabel =
    statusKey === "ready"
      ? t("sources.display.ready_badge")
      : t(`sources.display.${statusKey}`);

  const preview = detail?.preview_text ?? "";
  const showToggle = preview.length > 320;
  const previewText =
    expanded || !showToggle ? preview : `${preview.slice(0, 320).trim()}…`;

  const footer = detail ? (
    <>
      <Button variant="secondary" disabled={busy} onClick={() => onReindex(detail.id)}>
        <RefreshCw size={16} />
        {t("sources.reindex")}
      </Button>
      <a
        href={detail.url}
        target="_blank"
        rel="noreferrer"
        className="ds-btn ds-btn--secondary"
      >
        <ExternalLink size={16} />
        {t("sources.open_url")}
      </a>
      <Button variant="danger" disabled={busy} onClick={() => onDelete(detail.id)}>
        {t("sources.delete_source")}
      </Button>
    </>
  ) : undefined;

  return (
    <Drawer
      open={detail != null || loading}
      onClose={onClose}
      title={t("sources.drawer.title")}
      closeLabel={t("common.close")}
      mode="inline"
      footer={footer}
    >
      {loading && !detail ? (
        <LoadingState label={t("common.loading")} />
      ) : detail ? (
        <>
          <StatusBadge variant={badgeVariant} label={badgeLabel} size="md" />

          {detail.error_message && (
            <p className="ds-source-error-note">{detail.error_message}</p>
          )}

          <dl className="ds-meta-list">
            <div>
              <dt>{t("sources.col.title")}</dt>
              <dd>{detail.title || t("common.dash")}</dd>
            </div>
            <div>
              <dt>{t("sources.col.url")}</dt>
              <dd>
                <a href={detail.url} target="_blank" rel="noreferrer">
                  {detail.url}
                </a>
              </dd>
            </div>
            <div>
              <dt>{t("sources.col.type")}</dt>
              <dd>{t(`sources.type.${sourceTypeKey(detail)}` as "sources.type.page")}</dd>
            </div>
            <div>
              <dt>{t("sources.col.indexed_at")}</dt>
              <dd>{formatDateTime(detail.indexed_at, lang)}</dd>
            </div>
            <div>
              <dt>{t("sources.drawer.last_checked")}</dt>
              <dd>{formatDateTime(detail.last_checked_at, lang)}</dd>
            </div>
            <div>
              <dt>{t("sources.col.chunks")}</dt>
              <dd>{detail.chunk_count ?? 0}</dd>
            </div>
            <div>
              <dt>{t("sources.drawer.words")}</dt>
              <dd>{detail.word_count}</dd>
            </div>
            <div>
              <dt>{t("sources.drawer.chars")}</dt>
              <dd>{detail.char_count}</dd>
            </div>
            <div>
              <dt>{t("sources.drawer.doc_type")}</dt>
              <dd>{detail.document_type || t("common.dash")}</dd>
            </div>
            <div>
              <dt>{t("sources.drawer.ai_hint")}</dt>
              <dd>{detail.content_type_hint || t("common.dash")}</dd>
            </div>
          </dl>

          {preview && (
            <section>
              <h3 className="ds-h3" style={{ marginBottom: 8 }}>
                {t("sources.drawer.preview")}
              </h3>
              <p className="ds-body2">{previewText}</p>
              {showToggle && (
                <Button variant="ghost" size="sm" onClick={() => setExpanded((v) => !v)}>
                  {expanded ? t("sources.drawer.show_less") : t("sources.drawer.show_more")}
                </Button>
              )}
            </section>
          )}

          <SourceIntelligencePanel
            profile={detail.semantic_profile}
            summary={detail.llm_summary}
            profileVersion={detail.profile_version}
          />
        </>
      ) : null}
    </Drawer>
  );
}
