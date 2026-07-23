import { useCallback, useEffect, useState } from "react";
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
} from "../api/client";
import AnalyticsHeader from "../components/analytics/AnalyticsHeader";
import AnalyticsKpiSection from "../components/analytics/AnalyticsKpiSection";
import AnalyticsTrendsSection from "../components/analytics/AnalyticsTrendsSection";
import DistributionBarChart from "../components/analytics/DistributionBarChart";
import {
  AiInsightsSection,
  RecommendationsSection,
} from "../components/analytics/InsightsSections";
import PopularQueriesSection from "../components/analytics/PopularQueriesSection";
import ProblematicQueriesSection from "../components/analytics/ProblematicQueriesSection";
import RetrievalQualitySection from "../components/analytics/RetrievalQualitySection";
import SourceAnalyticsSection from "../components/analytics/SourceAnalyticsSection";
import { useTranslation } from "../i18n";
import { intentLabel } from "../lib/intentLabel";
import { Alert, PageLayout } from "../ui";
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
} from "../types";

const PERIOD_DAYS = 7;

export default function AnalyticsPage() {
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

  const load = useCallback(async (search = querySearch) => {
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
        getSourceAnalytics(15, 15),
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
    }
  }, [querySearch]);

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

  const intentLabelFn = (intent: string) => intentLabel(intent, t);

  return (
    <PageLayout className="ds-analytics-page">
      <AnalyticsHeader
        title={t("analytics.title")}
        subtitle={t("analytics.subtitle_product")}
        updatedAt={updatedAt}
        updatedLabel={t("analytics.updated")}
        refreshLabel={t("analytics.refresh")}
        timeframeLabel={t("analytics.timeframe_7d")}
        onRefresh={() => void onRefresh()}
        refreshing={refreshing}
      />

      {errorKey && <Alert variant="error">{t(errorKey)}</Alert>}

      {summary && (
        <AnalyticsKpiSection summary={summary} pct={pct} msLabel={msLabel} />
      )}

      <AnalyticsTrendsSection timeseries={timeseries} msLabel={msLabel} pct={pct} />

      <PopularQueriesSection
        rows={popular}
        pct={pct}
        msLabel={msLabel}
        onSearch={onSearchQueries}
        searching={searching}
      />

      <ProblematicQueriesSection rows={problematic} />

      {retrieval && (
        <RetrievalQualitySection metrics={retrieval} pct={pct} msLabel={msLabel} />
      )}

      {sources && <SourceAnalyticsSection data={sources} />}

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

      {insightsPayload && (
        <div className="an-tables-row">
          <AiInsightsSection insights={insightsPayload.insights} />
          <RecommendationsSection recommendations={insightsPayload.recommendations} />
        </div>
      )}
    </PageLayout>
  );
}
