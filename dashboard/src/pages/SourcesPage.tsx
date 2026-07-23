import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  bulkDeleteSources,
  bulkReindexSources,
  bulkResetSourceStatus,
  deleteSource,
  exportSources,
  getOverview,
  getIndexStatus,
  getSource,
  listSources,
  reindexSource,
  startIndexing,
} from "../api/client";
import SourceDetailDrawer from "../components/sources/SourceDetailDrawer";
import SourcesBulkBar from "../components/sources/SourcesBulkBar";
import SourcesFilters, {
  EMPTY_FILTERS,
  type SourceFilterValues,
} from "../components/sources/SourcesFilters";
import SourcesHeader from "../components/sources/SourcesHeader";
import SourcesIndexingBanner from "../components/sources/SourcesIndexingBanner";
import SourcesKnowledgeMiniCard from "../components/sources/SourcesKnowledgeMiniCard";
import SourcesPagination from "../components/sources/SourcesPagination";
import SourcesSummaryCards from "../components/sources/SourcesSummaryCards";
import SourcesTable, { type MenuAction } from "../components/sources/SourcesTable";
import { useTranslation } from "../i18n";
import { indexJobErrorMessage, sleep } from "../lib/indexJobUtils";
import { Alert, PageLayout, Toast } from "../ui";
import type { IndexJobStatus, KnowledgeBaseStatus, Source, SourceDetail } from "../types";

const DEFAULT_PAGE_SIZE = 50;

export default function SourcesPage() {
  const { t, lang, indexingStageLabel } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [filters, setFilters] = useState<SourceFilterValues>(EMPTY_FILTERS);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBaseStatus | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SourceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [indexStatus, setIndexStatus] = useState<IndexJobStatus | null>(null);
  const prevIndexStatus = useRef<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedFilters(filters), 300);
    return () => window.clearTimeout(timer);
  }, [filters]);

  useEffect(() => {
    if (window.matchMedia("(max-width: 768px)").matches) {
      setFiltersCollapsed(true);
    }
  }, []);

  const queryParams = useMemo(
    () => ({
      page,
      page_size: pageSize,
      search: debouncedFilters.search.trim() || undefined,
      bucket: debouncedFilters.bucket || undefined,
      source_type: debouncedFilters.source_type || undefined,
      url_contains: debouncedFilters.url_contains.trim() || undefined,
      date_range: debouncedFilters.date_range || undefined,
    }),
    [page, pageSize, debouncedFilters]
  );

  const loadOverview = useCallback(async () => {
    try {
      const overview = await getOverview();
      setKnowledgeBase(overview.knowledge_base);
    } catch {
      /* optional */
    }
  }, []);

  const loadSources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listSources(queryParams);
      setSources(res.items);
      setTotal(res.total);
      setPage(res.page);
      setErrorKey(null);
    } catch {
      setErrorKey("sources.error_load");
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadSources(), loadOverview()]);
  }, [loadSources, loadOverview]);

  useEffect(() => {
    const current = indexStatus?.status ?? null;
    if (prevIndexStatus.current === "running" && current !== "running") {
      void refreshAll();
    }
    prevIndexStatus.current = current;
  }, [indexStatus?.status, refreshAll]);

  useEffect(() => {
    void loadOverview();
    const poll = window.setInterval(() => {
      getIndexStatus()
        .then(setIndexStatus)
        .catch(() => {
          /* optional */
        });
    }, 5000);
    getIndexStatus()
      .then(setIndexStatus)
      .catch(() => {
        /* optional */
      });
    return () => window.clearInterval(poll);
  }, [loadOverview]);

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  useEffect(() => {
    setPage(1);
  }, [debouncedFilters]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const openDetail = async (source: Source) => {
    setActiveId(source.id);
    setDetailLoading(true);
    try {
      const d = await getSource(source.id);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setActiveId(null);
    setDetail(null);
  };

  const onFilterChange = (patch: Partial<SourceFilterValues>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const onResetFilters = () => {
    setFilters(EMPTY_FILTERS);
  };

  const toggleSelected = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    if (checked) setSelected(new Set(sources.map((s) => s.id)));
    else setSelected(new Set());
  };

  const clearSelection = () => setSelected(new Set());

  const runBulk = async (fn: (ids: number[]) => Promise<unknown>) => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    setBusy(true);
    try {
      await fn(ids);
      clearSelection();
      await refreshAll();
      if (activeId != null && !ids.includes(activeId)) {
        /* keep drawer */
      } else if (activeId != null && ids.includes(activeId)) {
        closeDetail();
      }
    } finally {
      setBusy(false);
    }
  };

  const onReindexOne = async (id: number) => {
    setBusy(true);
    try {
      await reindexSource(id);
      await refreshAll();
      if (activeId === id) {
        const d = await getSource(id);
        setDetail(d);
      }
    } finally {
      setBusy(false);
    }
  };

  const onDeleteOne = async (id: number) => {
    if (!confirm(t("sources.delete_confirm"))) return;
    setBusy(true);
    try {
      await deleteSource(id);
      if (activeId === id) closeDetail();
      await refreshAll();
    } finally {
      setBusy(false);
    }
  };

  const onMenuAction = async (action: MenuAction, source: Source) => {
    switch (action) {
      case "reindex":
        await onReindexOne(source.id);
        break;
      case "open":
        window.open(source.url, "_blank", "noopener,noreferrer");
        break;
      case "copy":
        await navigator.clipboard.writeText(source.url);
        setToast(t("sources.copied"));
        break;
      case "delete":
        await onDeleteOne(source.id);
        break;
      case "details":
        await openDetail(source);
        break;
      default:
        break;
    }
  };

  const onIndexAllPending = async () => {
    if (indexStatus?.status === "running") {
      setIndexError(t("sources.indexing_already_running"));
      return;
    }
    setIndexing(true);
    setIndexError(null);
    setErrorKey(null);
    try {
      await startIndexing({ pending_only: true });
      let latest: IndexJobStatus | null = null;
      for (let i = 0; i < 12; i += 1) {
        await sleep(400);
        latest = await getIndexStatus();
        setIndexStatus(latest);
        if (latest.status !== "running") break;
      }
      if (latest?.status === "failed") {
        setIndexError(
          indexJobErrorMessage(latest) || t("sources.indexing_failed")
        );
      } else if (latest?.status === "running") {
        setToast(t("sources.index_started"));
      } else if (latest?.status === "completed") {
        setToast(t("sources.index_completed"));
        await refreshAll();
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setIndexError(err?.response?.data?.detail || t("sources.error_load"));
    } finally {
      setIndexing(false);
    }
  };

  const onExport = async () => {
    try {
      await exportSources();
    } catch {
      setErrorKey("sources.error_load");
    }
  };

  const drawerOpen = activeId != null;
  const indexingRunning = indexStatus?.status === "running";

  return (
    <PageLayout>
      <SourcesHeader
        title={t("sources.title")}
        subtitle={t("sources.subtitle")}
        refreshLabel={t("sources.refresh")}
        exportLabel={t("sources.export")}
        indexLabel={t("sources.index_all_pending")}
        loading={loading}
        indexing={indexing || indexingRunning}
        onRefresh={() => void refreshAll()}
        onExport={() => void onExport()}
        onIndexAll={() => void onIndexAllPending()}
      />

      {errorKey && <Alert variant="error">{t(errorKey)}</Alert>}
      {indexError && <Alert variant="error">{indexError}</Alert>}
      {toast && <Toast>{toast}</Toast>}

      <SourcesIndexingBanner status={indexStatus} t={t} indexingStageLabel={indexingStageLabel} />

      <SourcesSummaryCards data={knowledgeBase} lang={lang} t={t} />

      <SourcesFilters
        values={filters}
        collapsed={filtersCollapsed}
        t={t}
        onChange={onFilterChange}
        onReset={onResetFilters}
        onToggleCollapse={() => setFiltersCollapsed((v) => !v)}
      />

      <div className="ds-page-split">
        <div className="ds-page-split__main">
          <SourcesTable
            sources={sources}
            selected={selected}
            loading={loading}
            lang={lang}
            t={t}
            activeId={activeId}
            toolbar={
              <SourcesBulkBar
                count={selected.size}
                busy={busy}
                t={t}
                onReindex={() => void runBulk((ids) => bulkReindexSources(ids))}
                onDelete={() => {
                  if (!confirm(t("sources.bulk.delete_confirm", { count: selected.size }))) return;
                  void runBulk((ids) => bulkDeleteSources(ids));
                }}
                onReset={() => void runBulk((ids) => bulkResetSourceStatus(ids))}
                onClear={clearSelection}
              />
            }
            onToggle={toggleSelected}
            onToggleAll={toggleAll}
            onRowClick={(s) => void openDetail(s)}
            onMenuAction={(action, source) => void onMenuAction(action, source)}
          />

          <SourcesPagination
            page={page}
            pageSize={pageSize}
            total={total}
            lang={lang}
            t={t}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </div>

        {drawerOpen && (
          <SourceDetailDrawer
            detail={detail}
            loading={detailLoading}
            lang={lang}
            t={t}
            busy={busy}
            onClose={closeDetail}
            onReindex={(id) => void onReindexOne(id)}
            onDelete={(id) => void onDeleteOne(id)}
          />
        )}
      </div>

      {knowledgeBase && (
        <SourcesKnowledgeMiniCard data={knowledgeBase} lang={lang} t={t} />
      )}
    </PageLayout>
  );
}
