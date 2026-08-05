import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getChatLogs,
  getHealth,
  getIndexStatus,
  getOverview,
  getSettings,
  listSources,
} from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useTranslation } from "../../i18n";
import {
  deriveHomeModel,
  healthChecklistCopyKey,
  type HomeChecklistTone,
} from "../../lib/homeReadiness";
import { canAccessRoute } from "../../lib/permissions";
import type { ChatLog, HealthResponse, IndexJobStatus, KnowledgeBaseStatus, Settings } from "../../types";
import {
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
  PageLayout,
  SectionCard,
  StatusBadge,
  type StatusVariant,
} from "../../ui";

function toneVariant(tone: HomeChecklistTone): StatusVariant {
  if (tone === "ready") return "ready";
  if (tone === "processing") return "processing";
  if (tone === "attention") return "warning";
  return "pending";
}

const MORE_LINKS = [
  { to: "/ask", labelKey: "home.action.ask" },
  { to: "/knowledge/library", labelKey: "home.action.review_library" },
  { to: "/insights/performance", labelKey: "home.action.view_performance" },
  { to: "/settings/general", labelKey: "home.action.open_settings" },
] as const;

export default function HomeScreen() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const role = user?.role;

  const [settings, setSettings] = useState<Settings | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [job, setJob] = useState<IndexJobStatus | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBaseStatus | null>(null);
  const [sourceCount, setSourceCount] = useState(0);
  const [recent, setRecent] = useState<ChatLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, h, j, srcs, overview, logs] = await Promise.all([
        getSettings(),
        getHealth(),
        getIndexStatus(),
        listSources({ page: 1, page_size: 1 }),
        getOverview().catch(() => null),
        getChatLogs(1, 5).catch(() => null),
      ]);
      setSettings(s);
      setHealth(h);
      setJob(j);
      setSourceCount(srcs.total);
      setKnowledgeBase(overview?.knowledge_base ?? null);
      setRecent(logs?.items ?? []);
      setErrorKey(null);
    } catch {
      setErrorKey("home.error_description");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const model = useMemo(
    () => deriveHomeModel({ settings, health, job, knowledgeBase, sourceCount }),
    [settings, health, job, knowledgeBase, sourceCount]
  );
  const { state, buckets, primary, secondary, healthOk, askReady, verdictTone } = model;

  const canSeeRoute = (to: string) => !role || canAccessRoute(role, to);

  const badgeLabel = (tone: HomeChecklistTone): string => {
    if (tone === "ready") return t("home.badge.ready");
    if (tone === "processing") return t("home.badge.processing");
    if (tone === "attention") return t("home.badge.attention");
    return t("home.badge.unknown");
  };

  const knowledgeText = (() => {
    const base = { ready: buckets.readyToUse, total: buckets.relevantTotal };
    if (buckets.failed > 0) {
      return t("home.checklist.knowledge_failures", { ...base, failed: buckets.failed });
    }
    if (buckets.waiting > 0) {
      return t("home.checklist.knowledge_waiting", { ...base, waiting: buckets.waiting });
    }
    if (buckets.needsRefresh > 0) {
      return t("home.checklist.knowledge_refresh", { ...base, refresh: buckets.needsRefresh });
    }
    if (buckets.skipped > 0) {
      return t("home.checklist.knowledge_summary_skipped", { ...base, skipped: buckets.skipped });
    }
    return t("home.checklist.knowledge_summary", base);
  })();

  const attentionItems = [
    {
      tone: model.siteTone,
      text: settings?.site_url ? t("home.checklist.site") : t("home.checklist.site_missing"),
    },
    { tone: model.knowledgeTone, text: knowledgeText },
    { tone: model.healthTone, text: t(healthChecklistCopyKey(healthOk)) },
    {
      tone: model.askTone,
      text: askReady ? t("home.checklist.ask_ready") : t("home.checklist.ask_not_ready"),
    },
  ];

  const checklistVisible =
    state === "ready" ? attentionItems.filter((item) => item.tone !== "ready") : attentionItems;

  const secondaryLinks = MORE_LINKS.filter(
    (link) => link.to !== primary.to && link.to !== secondary?.to && canSeeRoute(link.to)
  );

  return (
    <PageLayout className="ds-home">
      <PageHeader title={t("home.title")} subtitle={t("home.subtitle")} />

      {loading && <LoadingState label={t("common.loading")} />}

      {!loading && errorKey && (
        <ErrorState
          title={t("home.error_title")}
          description={t(errorKey)}
          action={
            <Button variant="secondary" onClick={() => void load()}>
              {t("home.retry")}
            </Button>
          }
        />
      )}

      {!loading && !errorKey && (
        <>
          <section className={`ds-home__verdict ds-home__verdict--${state}`} aria-live="polite">
            <div className="ds-home__verdict-copy">
              <StatusBadge variant={toneVariant(verdictTone)} label={badgeLabel(verdictTone)} size="md" />
              <h2 className="ds-home__verdict-title">{t(`home.state.${state}.title`)}</h2>
              <p className="ds-home__verdict-desc">{t(`home.state.${state}.description`)}</p>
              <div className="ds-home__verdict-actions">
                {canSeeRoute(primary.to) && (
                  <Link to={primary.to}>
                    <Button variant="primary">{t(primary.labelKey)}</Button>
                  </Link>
                )}
                {secondary && canSeeRoute(secondary.to) && (
                  <Link to={secondary.to}>
                    <Button variant="secondary">{t(secondary.labelKey)}</Button>
                  </Link>
                )}
              </div>
            </div>
          </section>

          <div className="ds-home__metrics" role="group" aria-label={t("home.metrics.title")}>
            <div className="ds-home__metric">
              <span className="ds-home__metric-label">{t("home.metrics.sources")}</span>
              <span className="ds-home__metric-value">
                {buckets.readyToUse}
                <span className="ds-home__metric-hint"> / {buckets.relevantTotal}</span>
              </span>
              <span className="ds-home__metric-hint">
                {buckets.skipped > 0
                  ? t("home.metrics.sources_hint_skipped", { skipped: buckets.skipped })
                  : t("home.metrics.sources_hint")}
              </span>
            </div>
            <div className="ds-home__metric">
              <span className="ds-home__metric-label">{t("home.metrics.health")}</span>
              <span className="ds-home__metric-value">{badgeLabel(model.healthTone)}</span>
              <span className="ds-home__metric-hint">{t("home.metrics.health_hint")}</span>
            </div>
            <div className="ds-home__metric">
              <span className="ds-home__metric-label">{t("home.metrics.index")}</span>
              <span className="ds-home__metric-value">
                {job?.status === "running" ? t("home.badge.processing") : t("home.metrics.index_idle")}
              </span>
              <span className="ds-home__metric-hint">{t("home.metrics.index_hint")}</span>
            </div>
          </div>

          <div className="ds-home__grid">
            <SectionCard
              title={
                checklistVisible.length === 0
                  ? t("home.checklist.clear_title")
                  : t("home.checklist.attention_title")
              }
              subtitle={
                checklistVisible.length === 0
                  ? t("home.checklist.clear_subtitle")
                  : t("home.checklist.attention_subtitle")
              }
            >
              {checklistVisible.length === 0 ? (
                <p className="ds-help">{t("home.checklist.all_clear")}</p>
              ) : (
                <ul className="ds-home__checklist">
                  {checklistVisible.map((item) => (
                    <li key={item.text} className="ds-home__checklist-item">
                      <StatusBadge variant={toneVariant(item.tone)} label={badgeLabel(item.tone)} />
                      <span>{item.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard
              title={t("home.recent.title")}
              subtitle={t("home.recent.subtitle")}
              actions={
                canSeeRoute("/insights/activity") ? (
                  <Link to="/insights/activity">
                    <Button variant="ghost" size="sm">
                      {t("home.recent.view_all")}
                    </Button>
                  </Link>
                ) : undefined
              }
            >
              {recent.length === 0 ? (
                <p className="ds-help">{t("home.recent.empty")}</p>
              ) : (
                <ul className="ds-home__activity-list">
                  {recent.map((log) => (
                    <li key={log.id} className="ds-home__activity-item">
                      <span className="ds-home__activity-q">{log.user_message}</span>
                      <span className="ds-home__activity-meta">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : t("common.dash")}
                        {" · "}
                        {log.used_context
                          ? t("home.recent.with_sources", { count: log.sources?.length ?? 0 })
                          : t("home.recent.no_sources")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>

          {secondaryLinks.length > 0 && (
            <SectionCard title={t("home.quick_links.title")} subtitle={t("home.quick_links.subtitle")}>
              <div className="ds-home__links">
                {secondaryLinks.map((link) => (
                  <Link key={link.to} to={link.to}>
                    <Button variant="outline" size="sm">
                      {t(link.labelKey)}
                    </Button>
                  </Link>
                ))}
              </div>
            </SectionCard>
          )}
        </>
      )}
    </PageLayout>
  );
}
