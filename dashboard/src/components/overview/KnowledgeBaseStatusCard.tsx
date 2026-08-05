import { Link } from "react-router-dom";
import type { KnowledgeBaseStatus } from "../../types";
import { Button } from "../../ui";

type Props = {
  data: KnowledgeBaseStatus;
  t: (key: string, params?: Record<string, string | number>) => string;
};

function MetricTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="ds-kb-metric">
      <div className="ds-kb-metric__value">{value}</div>
      <div className="ds-kb-metric__label">{label}</div>
    </div>
  );
}

export default function KnowledgeBaseStatusCard({ data, t }: Props) {
  const pct = Math.min(100, Math.max(0, data.readiness_percent));
  const notReady = data.ready_to_use === 0;
  const totalRelevant = data.ready_to_use + data.waiting + data.failed;

  return (
    <section className="ds-card ds-card--padding-md ds-kb-status">
      <div className="ds-kb-status__header">
        <h3 className="ds-kb-status__title">{t("overview.kb.title")}</h3>
      </div>

      {notReady ? (
        <div className="ds-kb-status__warning">
          <p className="ds-kb-status__summary">{t("overview.kb.not_ready")}</p>
          <Link to="/knowledge/update">
            <Button variant="primary" size="sm">
              {t("overview.kb.start_indexing")}
            </Button>
          </Link>
        </div>
      ) : (
        <p className="ds-kb-status__summary">
          {t("overview.kb.helper", {
            ready: data.ready_to_use,
            total: totalRelevant,
          })}
        </p>
      )}

      <div className="ds-kb-status__readiness">
        <div className="ds-kb-status__readiness-label">
          <span>{t("overview.kb.readiness")}</span>
          <strong>{pct.toFixed(1)}%</strong>
        </div>
        <div className="ds-kb-status__track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="ds-kb-status__fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="ds-kb-metrics">
        <MetricTile label={t("overview.kb.ready")} value={data.ready_to_use} />
        <MetricTile label={t("overview.kb.waiting")} value={data.waiting} />
        <MetricTile label={t("overview.kb.needs_refresh")} value={data.needs_refresh} />
        <MetricTile label={t("overview.kb.failed")} value={data.failed} />
        <MetricTile label={t("overview.kb.skipped")} value={data.skipped} />
      </div>

      <p className="ds-kb-status__meta">
        {t("overview.kb.total_sources")}: {data.total_sources} · {t("overview.kb.chunks")}:{" "}
        {data.chunks_count}
      </p>

      <div className="ds-kb-status__actions">
        <Link to="/knowledge/update">
          <Button variant="secondary" size="sm">
            {t("overview.kb.go_indexing")}
          </Button>
        </Link>
        <Link to="/knowledge/library">
          <Button variant="secondary" size="sm">
            {t("overview.kb.go_sources")}
          </Button>
        </Link>
      </div>
    </section>
  );
}
