import type { AnalyticsInsight, AnalyticsRecommendation } from "../../types";
import { SectionCard } from "../../ui";
import { useTranslation } from "../../i18n";

function Stars({ count }: { count: number }) {
  return (
    <span className="an-rec-stars" aria-label={`${count} stars`}>
      {"★".repeat(count)}
      {"☆".repeat(Math.max(0, 5 - count))}
    </span>
  );
}

export function AiInsightsSection({ insights }: { insights: AnalyticsInsight[] }) {
  const { t } = useTranslation();

  return (
    <SectionCard title={t("analytics.ai_insights")} subtitle={t("analytics.ai_insights_hint")}>
      {insights.length === 0 ? (
        <p className="ds-caption">{t("analytics.no_insights")}</p>
      ) : (
        <ul className="an-insights-list">
          {insights.map((item) => (
            <li key={item.id} className={`an-insight an-insight--${item.severity}`}>
              {t(item.message_key, item.params as Record<string, string | number>)}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export function RecommendationsSection({
  recommendations,
}: {
  recommendations: AnalyticsRecommendation[];
}) {
  const { t } = useTranslation();

  return (
    <SectionCard title={t("analytics.recommendations")} subtitle={t("analytics.recommendations_hint")}>
      {recommendations.length === 0 ? (
        <p className="ds-caption">{t("analytics.no_recommendations")}</p>
      ) : (
        <ul className="an-rec-list">
          {recommendations.map((item) => (
            <li key={item.id} className="an-rec-item">
              <Stars count={item.stars} />
              <span>{t(item.message_key, item.params as Record<string, string | number>)}</span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
