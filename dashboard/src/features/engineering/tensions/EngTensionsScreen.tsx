import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getEpistemicHealthSummary } from "../../../api/client";
import { useTranslation } from "../../../i18n";
import type { EpistemicHealthSummary } from "../../../types";
import {
  Button,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageHeader,
  PageLayout,
  SectionCard,
} from "../../../ui";

/**
 * S006 — Engineering owner for knowledge-issue navigation. The full
 * explorer already exists at `/diagnostics/epistemic-health`
 * (`EpistemicHealthPage`); this screen shows a plain-language summary and
 * links out rather than duplicating fetch/filter/pagination
 * (RFC-102 duplication ban).
 */
export default function EngTensionsScreen() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<EpistemicHealthSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getEpistemicHealthSummary()
      .then((s) => {
        if (!cancelled) setSummary(s);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageLayout className="ds-page--wide">
      <PageHeader title={t("nav.eng_tensions")} subtitle={t("eng.tensions.subtitle")} />

      <SectionCard title={t("eng.tensions.what_title")}>
        <p className="ds-help">{t("eng.tensions.what_body")}</p>
      </SectionCard>

      <SectionCard title={t("eng.tensions.why_title")}>
        <p className="ds-help">{t("eng.tensions.why_body")}</p>
      </SectionCard>

      {loading ? (
        <LoadingState label={t("common.loading")} />
      ) : (
        <>
          {summary && (
            <MetricGrid columns={3}>
              <MetricCard
                label={t("epistemic_health.metric.real_open")}
                value={summary.real_open_tensions}
                tone="warning"
                hover={false}
              />
              <MetricCard
                label={t("epistemic_health.metric.real_support_deficit")}
                value={summary.real_support_deficit_tensions}
                tone="warning"
                hover={false}
              />
              <MetricCard
                label={t("epistemic_health.metric.real_conflict")}
                value={summary.real_conflict_tensions}
                tone="warning"
                hover={false}
              />
            </MetricGrid>
          )}

          <SectionCard title={t("eng.tensions.explorer_title")}>
            <p className="ds-help">{t("eng.tensions.explorer_body")}</p>
            <Link to="/diagnostics/epistemic-health">
              <Button variant="primary">{t("eng.tensions.explorer_cta")}</Button>
            </Link>
          </SectionCard>
        </>
      )}
    </PageLayout>
  );
}
