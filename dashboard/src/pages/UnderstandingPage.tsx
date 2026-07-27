import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { listUnderstandingTensions } from "../api/client";
import { useTranslation } from "../i18n";
import {
  countTensions,
  fetchAllTensions,
  filterTensions,
  formatIdList,
  paginateTensions,
  resolveUnderstandingViewState,
  tensionDiagnosticJson,
  tensionRowKey,
  type TensionFilter,
} from "../lib/understandingTensions";
import {
  Alert,
  Button,
  CodeBlock,
  FilterBar,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageHeader,
  PageLayout,
  Pagination,
  SectionCard,
  StatusBadge,
} from "../ui";
import type { TensionRecord } from "../types";

const PAGE_SIZE = 25;

export default function UnderstandingPage() {
  const { t } = useTranslation();
  const [allItems, setAllItems] = useState<TensionRecord[]>([]);
  const [filter, setFilter] = useState<TensionFilter>("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = (await fetchAllTensions(listUnderstandingTensions)) as TensionRecord[];
      setAllItems(items);
      setPage(1);
      setExpandedKey(null);
    } catch {
      setError(t("understanding.error_load"));
      setAllItems([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(() => countTensions(allItems), [allItems]);
  const filtered = useMemo(() => filterTensions(allItems, filter), [allItems, filter]);
  const paged = useMemo(
    () => paginateTensions(filtered, page, PAGE_SIZE),
    [filtered, page]
  );

  const viewState = resolveUnderstandingViewState({
    loading,
    error,
    itemCount: paged.items.length,
  });

  const typeLabel = useCallback(
    (tensionType: string) => {
      const key = `understanding.type.${tensionType}`;
      const labeled = t(key);
      return labeled === key ? tensionType : labeled;
    },
    [t]
  );

  function onFilterChange(next: TensionFilter) {
    setFilter(next);
    setPage(1);
    setExpandedKey(null);
  }

  async function onCopyJson(item: TensionRecord) {
    try {
      await navigator.clipboard.writeText(tensionDiagnosticJson(item));
      setCopyStatus(t("understanding.copy_ok"));
    } catch {
      setCopyStatus(t("understanding.copy_fail"));
    }
    window.setTimeout(() => setCopyStatus(null), 2000);
  }

  return (
    <PageLayout>
      <PageHeader
        title={t("understanding.title")}
        subtitle={t("understanding.subtitle")}
        actions={
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            {t("common.refresh")}
          </Button>
        }
      />

      <Alert variant="info">{t("understanding.banner")}</Alert>

      <MetricGrid columns={4}>
        <MetricCard
          label={t("understanding.metric.total")}
          value={counts.total}
          tone="info"
          hover={false}
          helper={t("understanding.metric.total_help")}
        />
        <MetricCard
          label={t("understanding.metric.support_deficit")}
          value={counts.support_deficit}
          tone="neutral"
          hover={false}
        />
        <MetricCard
          label={t("understanding.metric.conflict")}
          value={counts.conflict}
          tone="warning"
          hover={false}
        />
        <MetricCard
          label={t("understanding.metric.page")}
          value={`${paged.page} / ${paged.totalPages}`}
          tone="primary"
          hover={false}
          helper={t("understanding.metric.page_help", {
            shown: paged.items.length,
            filtered: filtered.length,
          })}
        />
      </MetricGrid>

      <FilterBar>
        <Button
          variant={filter === "all" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("all")}
        >
          {t("understanding.filter.all")}
        </Button>
        <Button
          variant={filter === "support_deficit" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("support_deficit")}
        >
          {t("understanding.filter.support_deficit")}
        </Button>
        <Button
          variant={filter === "conflict" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("conflict")}
        >
          {t("understanding.filter.conflict")}
        </Button>
      </FilterBar>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {copyStatus ? <Alert variant="info">{copyStatus}</Alert> : null}

      {viewState === "loading" ? (
        <LoadingState label={t("understanding.loading")} />
      ) : viewState === "error" ? (
        <SectionCard title={t("understanding.empty_title")}>
          <p>{t("understanding.error_load")}</p>
        </SectionCard>
      ) : viewState === "empty" ? (
        <SectionCard title={t("understanding.empty_title")}>
          <p>{t("understanding.empty")}</p>
        </SectionCard>
      ) : (
        <div className="ds-stack" style={{ gap: "0.75rem" }}>
          {paged.items.map((item) => {
            const key = tensionRowKey(item);
            const open = expandedKey === key;
            return (
              <SectionCard
                key={key}
                title={typeLabel(item.tension_type)}
                actions={
                  <StatusBadge
                    variant={item.tension_type === "conflict" ? "warning" : "neutral"}
                    label={typeLabel(item.tension_type)}
                  />
                }
              >
                <p className="ds-text-secondary" style={{ marginTop: 0 }}>
                  {item.summary}
                </p>
                <dl className="ds-kv-grid">
                  <div className="ds-kv-grid__row">
                    <dt>{t("understanding.col.claims")}</dt>
                    <dd className="ds-kv-grid__mono">{formatIdList(item.claim_ids)}</dd>
                  </div>
                  <div className="ds-kv-grid__row">
                    <dt>{t("understanding.col.observations")}</dt>
                    <dd className="ds-kv-grid__mono">
                      {formatIdList(item.observation_ref_ids)}
                    </dd>
                  </div>
                  <div className="ds-kv-grid__row">
                    <dt>{t("understanding.col.evidence")}</dt>
                    <dd className="ds-kv-grid__mono">
                      {formatIdList(item.evidence_link_ids)}
                    </dd>
                  </div>
                </dl>

                <Button
                  variant="ghost"
                  size="sm"
                  aria-expanded={open}
                  onClick={() => setExpandedKey(open ? null : key)}
                >
                  <ChevronDown size={14} style={{ transform: open ? "rotate(180deg)" : undefined }} />
                  {open ? t("understanding.collapse") : t("understanding.expand")}
                </Button>

                {open ? (
                  <div className="ds-stack" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
                    <p>
                      <strong>{t("understanding.detail.summary")}</strong>
                      <br />
                      {item.summary}
                    </p>
                    <p>
                      <strong>{t("understanding.col.claims")}:</strong>{" "}
                      <code>{formatIdList(item.claim_ids)}</code>
                    </p>
                    <p>
                      <strong>{t("understanding.col.observations")}:</strong>{" "}
                      <code>{formatIdList(item.observation_ref_ids)}</code>
                    </p>
                    <p>
                      <strong>{t("understanding.col.evidence")}:</strong>{" "}
                      <code>{formatIdList(item.evidence_link_ids)}</code>
                    </p>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <strong>{t("understanding.detail.json")}</strong>
                      <Button variant="secondary" size="sm" onClick={() => void onCopyJson(item)}>
                        {t("understanding.copy_json")}
                      </Button>
                    </div>
                    <CodeBlock>{tensionDiagnosticJson(item)}</CodeBlock>
                  </div>
                ) : null}
              </SectionCard>
            );
          })}

          {paged.totalPages > 1 ? (
            <Pagination
              page={paged.page}
              pageSize={PAGE_SIZE}
              total={paged.total}
              onPageChange={(p) => {
                setPage(p);
                setExpandedKey(null);
              }}
              infoLabel={t("common.page_of", { page: paged.page, total: paged.totalPages })}
            />
          ) : null}
        </div>
      )}
    </PageLayout>
  );
}
