import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getAnalyticsSummary,
  getAnalyticsTimeseries,
  getHealth,
  getIndexStatus,
  getIntentDistribution,
  getOverview,
  getSettings,
  listSources,
} from "../api/client";

import AnalyticsPreviewRow from "../components/overview/AnalyticsPreviewRow";

import KnowledgeBaseStatusCard from "../components/overview/KnowledgeBaseStatusCard";
import LlmRuntimePanel from "../components/settings/LlmRuntimePanel";

import OverviewFooterNote from "../components/overview/OverviewFooterNote";

import OverviewHeader from "../components/overview/OverviewHeader";

import SubsystemHealthPanel, {
  type SubsystemGroup,
  type SubsystemItem,
} from "../components/overview/SubsystemHealthPanel";

import {

  IconBrain,

  IconChip,

  IconCube,

  IconDatabase,

  IconGlobe,

  IconNetwork,

  IconServer,

  IconSitemap,

  IconSync,

} from "../components/overview/icons";

import { useTranslation } from "../i18n";
import { intentLabel } from "../lib/intentLabel";
import { Alert, PageLayout } from "../ui";
import type {

  AnalyticsSummary,

  HealthResponse,

  IndexJobStatus,

  IntentDistributionRow,

  KnowledgeBaseStatus,

  Settings,

  TimeseriesPoint,

} from "../types";



export default function OverviewPage() {

  const { t, healthStatusLabel, jobStatusLabel, lang } = useTranslation();

  const [health, setHealth] = useState<HealthResponse | null>(null);

  const [settings, setSettings] = useState<Settings | null>(null);

  const [job, setJob] = useState<IndexJobStatus | null>(null);

  const [sourceCount, setSourceCount] = useState<number>(0);

  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBaseStatus | null>(null);

  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);

  const [intentDistribution, setIntentDistribution] = useState<IntentDistributionRow[]>([]);

  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);

  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const [refreshing, setRefreshing] = useState(false);

  const [errorKey, setErrorKey] = useState<string | null>(null);



  const load = useCallback(async () => {

    try {

      const [h, s, j, srcs, summary, ts, overview, intents] = await Promise.all([

        getHealth(),

        getSettings(),

        getIndexStatus(),

        listSources({ page: 1, page_size: 1 }),

        getAnalyticsSummary().catch(() => null),

        getAnalyticsTimeseries(24).catch(() => [] as TimeseriesPoint[]),

        getOverview().catch(() => null),

        getIntentDistribution(1).catch(() => [] as IntentDistributionRow[]),

      ]);

      setHealth(h);

      setSettings(s);

      setJob(j);

      setSourceCount(srcs.total);

      setKnowledgeBase(overview?.knowledge_base ?? null);

      setAnalytics(summary);

      setIntentDistribution(intents);

      setTimeseries(ts);

      setUpdatedAt(new Date());

      setErrorKey(null);

    } catch {

      setErrorKey("overview.error_load");

    }

  }, []);



  useEffect(() => {

    void load();

  }, [load]);



  const onRefresh = async () => {

    setRefreshing(true);

    await load();

    setRefreshing(false);

  };



  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

  const formatLatency = (ms: number) => {

    if (ms >= 1000) {

      const sec = ms / 1000;

      return lang === "uk" ? `${sec.toFixed(2)} сек` : `${sec.toFixed(2)} s`;

    }

    return lang === "uk" ? `${ms.toFixed(0)} мс` : `${ms.toFixed(0)} ms`;

  };



  const dash = t("common.dash");

  const labelIntent = (intent: string) => intentLabel(intent, t);



  const subsystemGroups = useMemo((): SubsystemGroup[] => {
    const healthItems: SubsystemItem[] = [];
    const configItems: SubsystemItem[] = [];

    if (health) {
      healthItems.push(
        {
          id: "backend",
          name: t("overview.subsystem.backend"),
          kind: "status",
          status: health.app.status,
          statusLabel: healthStatusLabel(health.app.status),
          icon: <IconServer size={18} />,
        },
        {
          id: "database",
          name: t("overview.subsystem.database"),
          kind: "status",
          status: health.database.status,
          statusLabel: healthStatusLabel(health.database.status),
          detail: health.database.detail?.trim() || null,
          icon: <IconDatabase size={18} />,
        },
        {
          id: "ollama",
          name: t("overview.subsystem.ollama"),
          kind: "status",
          status: health.ollama.status,
          statusLabel: healthStatusLabel(health.ollama.status),
          icon: <IconBrain size={18} />,
        },
        {
          id: "qdrant",
          name: t("overview.subsystem.qdrant"),
          kind: "status",
          status: health.qdrant.status,
          statusLabel: healthStatusLabel(health.qdrant.status),
          icon: <IconCube size={18} />,
        },
        {
          id: "indexing",
          name: t("overview.subsystem.indexing"),
          kind: "status",
          status: job?.status ?? "idle",
          statusLabel: jobStatusLabel(job?.status ?? "idle"),
          icon: <IconSync size={18} />,
        }
      );
    }

    if (settings) {
      configItems.push(
        {
          id: "site_url",
          name: t("overview.site_url"),
          kind: "link",
          href: settings.site_url,
          emptyLabel: dash,
          icon: <IconGlobe size={18} />,
        },
        {
          id: "sitemap_url",
          name: t("overview.sitemap_url"),
          kind: "link",
          href: settings.sitemap_url,
          emptyLabel: dash,
          icon: <IconSitemap size={18} />,
        },
        {
          id: "llm",
          name: t("overview.active_llm"),
          kind: "text",
          text: settings.llm_model,
          emptyLabel: dash,
          icon: <IconChip size={18} />,
        },
        {
          id: "embedding",
          name: t("overview.active_embedding"),
          kind: "text",
          text: settings.embedding_model,
          emptyLabel: dash,
          icon: <IconNetwork size={18} />,
        }
      );
    }

    return [
      { id: "health", title: t("overview.subsystem_group_health"), items: healthItems },
      { id: "config", title: t("overview.subsystem_group_config"), items: configItems },
    ];
  }, [health, settings, job, t, healthStatusLabel, jobStatusLabel, dash]);



  const errorText = errorKey ? t(errorKey) : null;



  return (

    <PageLayout>

      <OverviewHeader

        title={t("overview.title")}

        subtitle={t("overview.subtitle")}

        updatedAt={updatedAt}

        updatedLabel={t("overview.updated")}

        refreshLabel={t("overview.refresh")}

        onRefresh={() => void onRefresh()}

        refreshing={refreshing}

      />



      {errorText && <Alert variant="error">{errorText}</Alert>}



      {knowledgeBase && <KnowledgeBaseStatusCard data={knowledgeBase} t={t} />}



      <SubsystemHealthPanel
        title={t("overview.subsystem_details")}
        groups={subsystemGroups}
      />

      <LlmRuntimePanel variant="overview" />

      <AnalyticsPreviewRow

        statsTitle={t("overview.stats_title")}

        lineChartTitle={t("overview.chart_requests_24h")}

        intentsTitle={t("overview.chart_intents_24h")}

        intentsHint={t("overview.chart_intents_hint")}

        emptyLabel={t("common.no_data_period")}

        sourceCount={knowledgeBase?.total_sources ?? sourceCount}

        readyToUse={knowledgeBase?.ready_to_use}

        summary={analytics}

        timeseries={timeseries}

        intents={intentDistribution}

        statLabels={{

          sources: t("overview.stat.ready_sources"),

          requests: t("overview.stat.requests"),

          latency: t("overview.stat.latency"),

          accuracy: t("overview.stat.accuracy"),

          cache: t("overview.stat.cache"),

          errors: t("overview.stat.errors"),

        }}

        deltaLabels={{

          today: t("overview.delta.today"),

          perDay: t("overview.delta.per_day"),

        }}

        formatLatency={formatLatency}

        formatPct={pct}

        labelIntent={labelIntent}
      />



      <OverviewFooterNote text={t("overview.footer")} />

    </PageLayout>

  );

}


