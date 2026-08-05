import { useEffect, useMemo, useState } from "react";
import { getChatLogs } from "../../../api/client";
import { useTranslation } from "../../../i18n";
import type { ChatLog } from "../../../types";
import {
  Button,
  DataTable,
  Field,
  FilterBar,
  Input,
  PageHeader,
  PageLayout,
  Pagination,
  StatusBadge,
} from "../../../ui";
import type { Column } from "../../../ui";

const PAGE_SIZE = 50;

export default function ActivityScreen() {
  const { t, cacheTypeLabel } = useTranslation();
  const [logs, setLogs] = useState<ChatLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [sessionFilter, setSessionFilter] = useState("");
  const [appliedSession, setAppliedSession] = useState<string | null>(null);

  const load = async (p = page, sessionId = appliedSession) => {
    setLoading(true);
    try {
      const res = await getChatLogs(p, PAGE_SIZE, sessionId);
      setLogs(res.items);
      setTotal(res.total);
      setPage(res.page);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(1, appliedSession);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedSession]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const columns: Column<ChatLog>[] = useMemo(
    () => [
      {
        id: "created_at",
        header: t("logs.col.created_at"),
        cell: (log) =>
          log.created_at ? new Date(log.created_at).toLocaleString() : t("common.dash"),
      },
      {
        id: "session_id",
        header: t("logs.col.session_id"),
        cell: (log) => (
          <span style={{ fontSize: 11, wordBreak: "break-all" }}>
            {log.session_id || t("common.dash")}
          </span>
        ),
      },
      {
        id: "request_id",
        header: t("logs.col.request_id"),
        cell: (log) => (
          <span style={{ fontSize: 11, wordBreak: "break-all" }}>
            {log.request_id || t("common.dash")}
          </span>
        ),
      },
      {
        id: "user_message",
        header: t("logs.col.user_message"),
        cell: (log) => log.user_message,
      },
      {
        id: "assistant_answer",
        header: t("logs.col.assistant_answer"),
        cell: (log) => log.assistant_answer,
      },
      {
        id: "used_context",
        header: t("logs.col.used_context"),
        cell: (log) => (
          <StatusBadge
            variant={log.used_context ? "ready" : "stopped"}
            label={log.used_context ? t("common.yes") : t("common.no")}
          />
        ),
      },
      {
        id: "cache",
        header: t("logs.col.cache"),
        cell: (log) =>
          log.cache_hit ? (
            <StatusBadge variant="completed" label={cacheTypeLabel(log.cache_type)} />
          ) : (
            <span className="ds-caption">{t("common.dash")}</span>
          ),
      },
      {
        id: "timing",
        header: t("logs.col.timing"),
        cell: (log) => (
          <span className="ds-caption">
            {t("logs.timing_prefix", {
              retrieval: log.retrieval_ms,
              generation: log.generation_ms,
            })}
            {log.polish_ms > 0 ? t("logs.timing_polish", { polish: log.polish_ms }) : ""}
          </span>
        ),
      },
      {
        id: "sources",
        header: t("logs.col.sources"),
        cell: (log) =>
          log.sources.length === 0 ? (
            <span className="ds-caption">{t("common.dash")}</span>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {log.sources.map((s, i) => (
                <li key={i}>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title || s.url}
                  </a>
                </li>
              ))}
            </ul>
          ),
      },
    ],
    [t, cacheTypeLabel]
  );

  return (
    <PageLayout>
      <PageHeader title={t("logs.title", { total })} subtitle={t("logs.subtitle")} />

      <FilterBar
        actions={
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            {loading ? t("common.loading") : t("common.refresh")}
          </Button>
        }
      >
        <Field label={t("logs.filter.session")}>
          <Input
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            placeholder={t("logs.filter.session")}
          />
        </Field>
        <Button
          variant="secondary"
          onClick={() => setAppliedSession(sessionFilter.trim() ? sessionFilter.trim() : null)}
        >
          {t("logs.filter.apply")}
        </Button>
      </FilterBar>

      <DataTable
        columns={columns}
        data={logs}
        keyFn={(log) => log.id}
        loading={loading}
        emptyTitle={t("logs.empty")}
        footer={
          totalPages > 1 ? (
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={(p) => void load(p)}
              infoLabel={t("common.page_of", { page, total: totalPages })}
            />
          ) : undefined
        }
      />
    </PageLayout>
  );
}
