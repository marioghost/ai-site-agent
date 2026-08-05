import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getHealth, getIndexStatus, getOverview, getSettings, listSources } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useTranslation } from "../../i18n";
import { canAccessRoute } from "../../lib/permissions";
import type { HealthResponse, IndexJobStatus, KnowledgeBaseStatus, Settings } from "../../types";
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

/** RFC-101 §7 readiness model — Home computes a single product state. */
type ReadinessState = "needs_setup" | "needs_update" | "updating" | "ready" | "needs_attention";

type Cta = { to: string; labelKey: string };

function isHealthOk(health: HealthResponse | null): boolean | null {
  if (!health) return null;
  return [health.app.status, health.database.status, health.ollama.status, health.qdrant.status].every(
    (status) => status.toLowerCase() === "ok"
  );
}

function computeReadinessState(params: {
  settings: Settings | null;
  health: HealthResponse | null;
  job: IndexJobStatus | null;
  knowledgeBase: KnowledgeBaseStatus | null;
  sourceCount: number;
}): ReadinessState {
  const { settings, health, job, knowledgeBase, sourceCount } = params;

  if (!settings?.site_url) return "needs_setup";
  if (job?.status === "running") return "updating";

  const totalSources = knowledgeBase?.total_sources ?? sourceCount;
  const readyToUse = knowledgeBase?.ready_to_use ?? 0;
  if (totalSources === 0 || readyToUse === 0) return "needs_update";

  const healthOk = isHealthOk(health);
  const hasFailures = (knowledgeBase?.failed ?? 0) > 0;
  if (healthOk === false || hasFailures) return "needs_attention";

  return "ready";
}

/** RFC-101 §7 — at most one primary CTA and one secondary CTA derived from state. */
function ctasForState(state: ReadinessState): { primary: Cta; secondary: Cta | null } {
  switch (state) {
    case "needs_setup":
      return { primary: { to: "/knowledge/site", labelKey: "home.action.go_site" }, secondary: null };
    case "needs_update":
      return {
        primary: { to: "/knowledge/update", labelKey: "home.action.update_knowledge" },
        secondary: null,
      };
    case "updating":
      return { primary: { to: "/knowledge/update", labelKey: "home.action.view_progress" }, secondary: null };
    case "needs_attention":
      return {
        primary: { to: "/knowledge/library", labelKey: "home.action.review_library" },
        secondary: { to: "/knowledge/update", labelKey: "home.action.update_knowledge" },
      };
    case "ready":
    default:
      return {
        primary: { to: "/ask", labelKey: "home.action.ask" },
        secondary: { to: "/insights/performance", labelKey: "home.action.view_performance" },
      };
  }
}

export default function HomeScreen() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const role = user?.role;

  const [settings, setSettings] = useState<Settings | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [job, setJob] = useState<IndexJobStatus | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBaseStatus | null>(null);
  const [sourceCount, setSourceCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, h, j, srcs, overview] = await Promise.all([
        getSettings(),
        getHealth(),
        getIndexStatus(),
        listSources({ page: 1, page_size: 1 }),
        getOverview().catch(() => null),
      ]);
      setSettings(s);
      setHealth(h);
      setJob(j);
      setSourceCount(srcs.total);
      setKnowledgeBase(overview?.knowledge_base ?? null);
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

  const state = useMemo(
    () => computeReadinessState({ settings, health, job, knowledgeBase, sourceCount }),
    [settings, health, job, knowledgeBase, sourceCount]
  );
  const { primary, secondary } = useMemo(() => ctasForState(state), [state]);

  const healthOk = isHealthOk(health);
  const totalSources = knowledgeBase?.total_sources ?? sourceCount;
  const readyToUse = knowledgeBase?.ready_to_use ?? 0;
  const askReady = state === "ready" || state === "needs_attention";

  const canSeeRoute = (to: string) => !role || canAccessRoute(role, to);

  const badgeVariant = (ok: boolean | null, hasProgress = false): StatusVariant => {
    if (ok === null) return "pending";
    if (ok) return "ready";
    return hasProgress ? "processing" : "failed";
  };
  const badgeLabel = (ok: boolean | null, hasProgress = false): string => {
    if (ok === null) return t("home.badge.unknown");
    if (ok) return t("home.badge.ready");
    return hasProgress ? t("home.badge.processing") : t("home.badge.attention");
  };

  return (
    <PageLayout>
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
          <SectionCard
            title={t(`home.state.${state}.title`)}
            subtitle={t(`home.state.${state}.description`)}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
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
          </SectionCard>

          <SectionCard title={t("home.checklist.title")}>
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              <li style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <StatusBadge
                  variant={badgeVariant(Boolean(settings?.site_url))}
                  label={badgeLabel(Boolean(settings?.site_url))}
                />
                <span>{settings?.site_url ? t("home.checklist.site") : t("home.checklist.site_missing")}</span>
              </li>
              <li style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <StatusBadge
                  variant={badgeVariant(readyToUse > 0, totalSources > 0)}
                  label={badgeLabel(readyToUse > 0, totalSources > 0)}
                />
                <span>
                  {t("home.checklist.knowledge_summary", { ready: readyToUse, total: totalSources })}
                </span>
              </li>
              <li style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <StatusBadge variant={badgeVariant(healthOk)} label={badgeLabel(healthOk)} />
                <span>{healthOk ? t("home.checklist.health") : t("home.checklist.health_degraded")}</span>
              </li>
              <li style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <StatusBadge variant={badgeVariant(askReady)} label={badgeLabel(askReady)} />
                <span>{askReady ? t("home.checklist.ask_ready") : t("home.checklist.ask_not_ready")}</span>
              </li>
            </ul>
          </SectionCard>

          <SectionCard title={t("home.quick_links.title")}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
              {canSeeRoute("/ask") && (
                <Link to="/ask">
                  <Button variant="outline" size="sm">
                    {t("home.action.ask")}
                  </Button>
                </Link>
              )}
              {canSeeRoute("/knowledge/update") && (
                <Link to="/knowledge/update">
                  <Button variant="outline" size="sm">
                    {t("home.action.update_knowledge")}
                  </Button>
                </Link>
              )}
              {canSeeRoute("/insights/performance") && (
                <Link to="/insights/performance">
                  <Button variant="outline" size="sm">
                    {t("home.action.view_performance")}
                  </Button>
                </Link>
              )}
              {canSeeRoute("/settings/general") && (
                <Link to="/settings/general">
                  <Button variant="outline" size="sm">
                    {t("home.action.open_settings")}
                  </Button>
                </Link>
              )}
            </div>
          </SectionCard>
        </>
      )}
    </PageLayout>
  );
}
