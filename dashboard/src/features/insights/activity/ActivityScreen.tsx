import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getChatLogs } from "../../../api/client";
import { useTranslation } from "../../../i18n";
import { filterActivityPage } from "../../../lib/activityFilter";
import type { ChatLog } from "../../../types";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  PageLayout,
  Pagination,
  StatusBadge,
} from "../../../ui";

const PAGE_SIZE = 25;

function truncate(text: string, max = 220): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
}

export default function ActivityScreen() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<ChatLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");

  const load = async (p = 1) => {
    setLoading(true);
    try {
      const res = await getChatLogs(p, PAGE_SIZE);
      setLogs(res.items);
      setTotal(res.total);
      setPage(res.page);
      setErrorKey(null);
    } catch {
      setErrorKey("activity.error_description");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(1);
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = useMemo(() => filterActivityPage(logs, appliedQuery), [logs, appliedQuery]);
  const hasQuery = appliedQuery.trim().length > 0;

  const clearSearch = () => {
    setQuery("");
    setAppliedQuery("");
  };

  const onPageChange = (p: number) => {
    void load(p);
  };

  return (
    <PageLayout className="ds-page--wide">
      <PageHeader
        title={t("activity.title")}
        subtitle={t("activity.subtitle")}
        actions={
          <Link to="/ask">
            <Button variant="primary">{t("activity.ask_cta")}</Button>
          </Link>
        }
      />

      <div className="ds-activity-toolbar">
        <Field label={t("activity.filter.search_page")}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("activity.filter.search_placeholder")}
            aria-describedby="activity-search-scope"
            onKeyDown={(e) => {
              if (e.key === "Enter") setAppliedQuery(query);
            }}
          />
          <p id="activity-search-scope" className="ds-field__hint">
            {t("activity.filter.search_help")}
          </p>
        </Field>
        <Button variant="secondary" onClick={() => setAppliedQuery(query)}>
          {t("common.search")}
        </Button>
        {hasQuery && (
          <Button variant="outline" onClick={clearSearch}>
            {t("activity.filter.clear")}
          </Button>
        )}
        <Button variant="outline" onClick={() => void load(page)} disabled={loading}>
          {loading ? t("common.loading") : t("common.refresh")}
        </Button>
      </div>

      {errorKey ? (
        <ErrorState
          title={t("activity.error_title")}
          description={t(errorKey)}
          action={
            <Button variant="secondary" onClick={() => void load(page)}>
              {t("home.retry")}
            </Button>
          }
        />
      ) : loading && logs.length === 0 ? (
        <EmptyState title={t("common.loading")} />
      ) : total === 0 ? (
        <EmptyState
          title={t("activity.empty")}
          description={t("activity.empty_hint")}
          action={
            <Link to="/ask">
              <Button variant="primary">{t("activity.ask_cta")}</Button>
            </Link>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={t("activity.no_match")}
          description={t("activity.no_match_hint")}
          action={
            <Button variant="secondary" onClick={clearSearch}>
              {t("activity.filter.clear")}
            </Button>
          }
        />
      ) : (
        <div className="ds-activity-list" aria-busy={loading || undefined}>
          {hasQuery && (
            <p className="ds-caption" role="status">
              {t("activity.filter.page_results", {
                shown: filtered.length,
                page,
                totalPages,
              })}
            </p>
          )}
          {filtered.map((log) => {
            const sourceList = log.sources ?? [];
            const sourced = Boolean(log.used_context && sourceList.length > 0);
            return (
              <article key={log.id} className="ds-activity-card">
                <div className="ds-activity-card__top">
                  <time className="ds-activity-card__time" dateTime={log.created_at || undefined}>
                    {log.created_at ? new Date(log.created_at).toLocaleString() : t("common.dash")}
                  </time>
                  <div className="ds-activity-card__meta">
                    <StatusBadge
                      variant={sourced ? "ready" : "warning"}
                      label={
                        sourced
                          ? t("activity.status.sourced", { count: sourceList.length })
                          : t("activity.status.no_sources")
                      }
                    />
                    {log.cache_hit && (
                      <StatusBadge variant="completed" label={t("activity.status.cached")} />
                    )}
                  </div>
                </div>
                <h3 className="ds-activity-card__q">{log.user_message}</h3>
                <p className="ds-activity-card__a">{truncate(log.assistant_answer || "")}</p>
                <details className="ds-activity-card__details">
                  <summary>{t("activity.details")}</summary>
                  <p className="ds-activity-card__full">{log.assistant_answer}</p>
                  {sourceList.length > 0 && (
                    <ul className="ds-activity-card__sources">
                      {sourceList.map((s, i) => (
                        <li key={`${log.id}-src-${i}`}>
                          <a href={s.url} target="_blank" rel="noreferrer">
                            {s.title || s.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </details>
              </article>
            );
          })}
        </div>
      )}

      {!errorKey && totalPages > 1 && total > 0 && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={onPageChange}
          infoLabel={
            hasQuery
              ? t("activity.page_of_filtered", { page, total: totalPages })
              : t("common.page_of", { page, total: totalPages })
          }
        />
      )}
    </PageLayout>
  );
}
