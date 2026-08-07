import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getAnalyticsInsights,
  getAnalyticsTimeseries,
  getIntentDistribution,
  getPopularQueries,
  getProblematicQueries,
  getProductAnalyticsSummary,
  getRetrievalQuality,
  getSourceAnalytics,
  getTopicDistribution,
} from "../../../api/client";
import { useTranslation } from "../../../i18n";
import { intentLabel } from "../../../lib/intentLabel";
import { evaluatePerformancePresence } from "../../../lib/performanceAnalytics";
import { Alert, Button, LoadingState, PageLayout } from "../../../ui";
import type {
  AnalyticsInsightsPayload,
  IntentDistributionRow,
  PopularQueryRow,
  ProblematicQueryRow,
  ProductAnalyticsSummary,
  RetrievalQualityMetrics,
  SourceAnalyticsPayload,
  TimeseriesPoint,
  TopicDistributionRow,
} from "../../../types";
import AnalyticsHeader from "./widgets/AnalyticsHeader";
import AnalyticsKpiSection from "./widgets/AnalyticsKpiSection";
import AnalyticsTrendsSection from "./widgets/AnalyticsTrendsSection";
import DistributionBarChart from "./widgets/DistributionBarChart";
import { AiInsightsSection, RecommendationsSection } from "./widgets/InsightsSections";
import PopularQueriesSection from "./widgets/PopularQueriesSection";
import ProblematicQueriesSection from "./widgets/ProblematicQueriesSection";
import RetrievalQualitySection from "./widgets/RetrievalQualitySection";
import SourceAnalyticsSection from "./widgets/SourceAnalyticsSection";

const PERIOD_DAYS = 7;

export default function PerformanceScreen() {
  const { t, lang } = useTranslation();
  const [summary, setSummary] = useState<ProductAnalyticsSummary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [popular, setPopular] = useState<PopularQueryRow[]>([]);
  const [problematic, setProblematic] = useState<ProblematicQueryRow[]>([]);
  const [retrieval, setRetrieval] = useState<RetrievalQualityMetrics | null>(null);
  const [sources, setSources] = useState<SourceAnalyticsPayload | null>(null);
  const [intents, setIntents] = useState<IntentDistributionRow[]>([]);
  const [topics, setTopics] = useState<TopicDistributionRow[]>([]);
  const [insightsPayload, setInsightsPayload] = useState<AnalyticsInsightsPayload | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searching, setSearching] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [querySearch, setQuerySearch] = useState("");

  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const msLabel = (n: number) => {
    if (n >= 1000) {
      const sec = n / 1000;
      return lang === "uk" ? `${sec.toFixed(2)} сек` : `${sec.toFixed(2)} s`;
    }
    return lang === "uk" ? `${n.toFixed(0)} мс` : `${n.toFixed(0)} ms`;
  };

  const load = useCallback(
    async (search = querySearch) => {
      try {
        const [
          productSummary,
          ts,
          popularRows,
          problematicRows,
          retrievalMetrics,
          sourceData,
          intentRows,
          topicRows,
          insightsData,
        ] = await Promise.all([
          getProductAnalyticsSummary(PERIOD_DAYS),
          getAnalyticsTimeseries(PERIOD_DAYS * 24),
          getPopularQueries(20, search, 30),
          getProblematicQueries(20, 30),
          getRetrievalQuality(PERIOD_DAYS),
          getSourceAnalytics(15, 15, 30),
          getIntentDistribution(30),
          getTopicDistribution(30, 12),
          getAnalyticsInsights(PERIOD_DAYS),
        ]);
        setSummary(productSummary);
        setTimeseries(ts);
        setPopular(popularRows);
        setProblematic(problematicRows);
        setRetrieval(retrievalMetrics);
        setSources(sourceData);
        setIntents(intentRows);
        setTopics(topicRows);
        setInsightsPayload(insightsData);
        setUpdatedAt(new Date());
        setErrorKey(null);
      } catch {
        setErrorKey("analytics.error_load");
      } finally {
        setLoading(false);
      }
    },
    [querySearch]
  );

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 60000);
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onSearchQueries = async (search: string) => {
    setQuerySearch(search);
    setSearching(true);
    try {
      setPopular(await getPopularQueries(20, search, 30));
    } finally {
      setSearching(false);
    }
  };

  const presence = useMemo(
    () =>
      evaluatePerformancePresence({
        timeseries,
        popularCount: popular.length,
        problematicCount: problematic.length,
        retrieval,
        sources,
        intents,
        topics,
        insights: insightsPayload,
      }),
    [timeseries, popular.length, problematic.length, retrieval, sources, intents, topics, insightsPayload]
  );

  const intentLabelFn = (intent: string) => intentLabel(intent, t);

  return (
    <PageLayout className="ds-analytics-page ds-page--wide">
      <AnalyticsHeader
        title={t("nav.performance")}
        subtitle={t("analytics.subtitle_product")}
        updatedAt={updatedAt}
        updatedLabel={t("analytics.updated")}
        refreshLabel={t("analytics.refresh")}
        timeframeLabel={t("analytics.timeframe_7d")}
        onRefresh={() => void onRefresh()}
        refreshing={refreshing}
      />

      {errorKey && <Alert variant="error">{t(errorKey)}</Alert>}

      {loading && !updatedAt ? (
        <LoadingState label={t("common.loading")} />
      ) : presence.isEmpty ? (
        !errorKey ? (
          <div className="ds-insights-empty">
            <h2 className="ds-insights-empty__title">{t("analytics.empty_title")}</h2>
            <p className="ds-insights-empty__desc">{t("analytics.empty_body")}</p>
            <Link to="/ask">
              <Button variant="primary">{t("activity.ask_cta")}</Button>
            </Link>
          </div>
        ) : null
      ) : (
        <>
          {summary && (presence.hasTrend || presence.hasQuery) && (
            <AnalyticsKpiSection summary={summary} pct={pct} msLabel={msLabel} />
          )}
          {presence.hasTrend && (
            <AnalyticsTrendsSection timeseries={timeseries} msLabel={msLabel} pct={pct} />
          )}
          {(popular.length > 0 || searching) && (
            <PopularQueriesSection
              rows={popular}
              pct={pct}
              msLabel={msLabel}
              onSearch={onSearchQueries}
              searching={searching}
            />
          )}
          {problematic.length > 0 && <ProblematicQueriesSection rows={problematic} />}
          {presence.hasRetrieval && retrieval && (
            <RetrievalQualitySection metrics={retrieval} pct={pct} msLabel={msLabel} />
          )}
          {presence.hasSources && sources && <SourceAnalyticsSection data={sources} />}
          {presence.hasDistribution && (
            <div className="an-tables-row">
              <DistributionBarChart
                title={t("analytics.intent_distribution")}
                subtitle={t("analytics.intent_distribution_hint")}
                rows={intents.map((row) => ({
                  label: intentLabelFn(row.intent),
                  count: row.count,
                  share: row.share,
                }))}
                emptyLabel={t("common.no_data")}
                labelKey={(row) => row.label}
              />
              <DistributionBarChart
                title={t("analytics.topic_distribution")}
                subtitle={t("analytics.topic_distribution_hint")}
                rows={topics.map((row) => ({
                  label: row.topic_label,
                  count: row.count,
                  share: row.share,
                }))}
                emptyLabel={t("common.no_data")}
              />
            </div>
          )}
          {presence.hasInsights && insightsPayload && (
            <div className="an-tables-row">
              <AiInsightsSection insights={insightsPayload.insights} />
              <RecommendationsSection recommendations={insightsPayload.recommendations} />
            </div>
          )}
        </>
      )}
    </PageLayout>
  );
}
