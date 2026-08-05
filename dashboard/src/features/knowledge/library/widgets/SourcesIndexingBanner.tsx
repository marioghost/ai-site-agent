import { Link } from "react-router-dom";
import type { IndexJobStatus } from "../../../../types";
import { indexJobErrorMessage } from "../../../../lib/indexJobUtils";
import { mapIndexStatusToViewModel } from "../../../../lib/indexStatus";

type Props = {
  status: IndexJobStatus | null;
  t: (key: string, vars?: Record<string, string | number>) => string;
  indexingStageLabel: (stage: string) => string;
};

export default function SourcesIndexingBanner({ status, t, indexingStageLabel }: Props) {
  if (!status) return null;

  if (status.status === "failed" && status.run_mode === "pending_only") {
    const detail = indexJobErrorMessage(status);
    return (
      <div className="ds-index-banner ds-index-banner--error" role="alert">
        <div className="ds-index-banner__main">
          <strong>{t("sources.indexing_banner.failed_title")}</strong>
          <span className="ds-caption">
            {detail || t("sources.indexing_banner.failed_generic")}
          </span>
        </div>
        <Link to="/knowledge/update" className="ds-index-banner__link">
          {t("sources.indexing_banner.link")}
        </Link>
      </div>
    );
  }

  if (status.status !== "running") return null;

  const live = mapIndexStatusToViewModel(status);
  const isPendingRun = status.run_mode === "pending_only";

  const progressText = live.progress.isIndeterminate
    ? t("sources.indexing_banner.progress_indeterminate", {
        processed: live.progress.processedTotal,
        selected: live.progress.selectedTotal || live.summary.selectedPages,
      })
    : t("sources.indexing_banner.progress", {
        processed: live.progress.processedTotal,
        selected: live.progress.selectedTotal,
        percent: live.progress.percent ?? 0,
      });

  return (
    <div className="ds-index-banner" role="status">
      <div className="ds-index-banner__main">
        <strong>{t("sources.indexing_banner.title")}</strong>
        <span className="ds-caption">
          {isPendingRun
            ? t("sources.indexing_banner.pending_mode")
            : indexingStageLabel(live.stage)}
        </span>
        <span className="ds-caption">{progressText}</span>
        {live.currentUrl && (
          <span className="ds-caption">{live.currentUrl}</span>
        )}
      </div>
      <Link to="/knowledge/update" className="ds-index-banner__link">
        {t("sources.indexing_banner.link")}
      </Link>
    </div>
  );
}
