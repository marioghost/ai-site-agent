import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  getBuildInfo,
  getEpistemicHealthSummary,
  listUnderstandingTensions,
} from "../api/client";
import ArchitectureStatusVisual from "../components/epistemic/ArchitectureStatusVisual";
import CapabilityMaturitySection from "../components/epistemic/CapabilityMaturitySection";
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
  Tag,
} from "../ui";
import type {
  BuildInfo,
  EpistemicHealthSummary,
  ProvenanceScope,
  TensionRecord,
} from "../types";

const PAGE_SIZE = 25;

export default function EpistemicHealthPage() {
  const { t } = useTranslation();
  const [allItems, setAllItems] = useState<TensionRecord[]>([]);
  const [summary, setSummary] = useState<EpistemicHealthSummary | null>(null);
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [provenanceScope, setProvenanceScope] = useState<ProvenanceScope>("real");
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
      const [items, healthSummary, buildInfo] = await Promise.all([
        fetchAllTensions(listUnderstandingTensions, 200, provenanceScope) as Promise<
          TensionRecord[]
        >,
        getEpistemicHealthSummary(),
        getBuildInfo().catch(() => null),
      ]);
      setAllItems(items);
      setSummary(healthSummary);
      setBuild(buildInfo);
      setPage(1);
      setExpandedKey(null);
    } catch {
      setError(t("epistemic_health.error_load"));
      setAllItems([]);
    } finally {
      setLoading(false);
    }
  }, [provenanceScope, t]);

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

  const emptyIsRealOnly =
    provenanceScope === "real" &&
    summary != null &&
    summary.real_open_tensions === 0 &&
    summary.test_open_tensions > 0;

  const typeLabel = useCallback(
    (tensionType: string) => {
      const key = `epistemic_health.type.${tensionType}`;
      const labeled = t(key);
      if (labeled !== key) return labeled;
      const legacy = t(`understanding.type.${tensionType}`);
      return legacy === `understanding.type.${tensionType}` ? tensionType : legacy;
    },
    [t]
  );

  function onFilterChange(next: TensionFilter) {
    setFilter(next);
    setPage(1);
    setExpandedKey(null);
  }

  function onProvenanceChange(next: ProvenanceScope) {
    setProvenanceScope(next);
    setFilter("all");
    setPage(1);
    setExpandedKey(null);
  }

  async function onCopyJson(item: TensionRecord) {
    try {
      await navigator.clipboard.writeText(tensionDiagnosticJson(item));
      setCopyStatus(t("epistemic_health.copy_ok"));
    } catch {
      setCopyStatus(t("epistemic_health.copy_fail"));
    }
    window.setTimeout(() => setCopyStatus(null), 2000);
  }

  const shadowOn = summary?.memory_shadow_write_enabled === true;

  return (
    <PageLayout>
      <PageHeader
        title={t("epistemic_health.title")}
        subtitle={t("epistemic_health.subtitle")}
        actions={
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            {t("common.refresh")}
          </Button>
        }
      />

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          alignItems: "center",
          marginBottom: "0.25rem",
        }}
      >
        <StatusBadge variant="processing" label={t("epistemic_health.badge.experimental")} />
        <StatusBadge variant="neutral" label={t("epistemic_health.badge.diagnostic_only")} />
        <StatusBadge
          variant="skipped"
          label={t("epistemic_health.badge.chat_impact_not_active")}
        />
        <StatusBadge
          variant={shadowOn ? "warning" : "ready"}
          label={
            shadowOn
              ? t("epistemic_health.badge.shadow_on")
              : t("epistemic_health.badge.shadow_off")
          }
        />
      </div>

      <Alert variant="info">{t("epistemic_health.banner")}</Alert>

      {summary ? (
        <>
          <MetricGrid columns={4}>
            <MetricCard
              label={t("epistemic_health.metric.real_claims")}
              value={summary.real_claims}
              tone="info"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.real_observations")}
              value={summary.real_observations}
              tone="neutral"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.real_evidence")}
              value={summary.real_evidence_links}
              tone="neutral"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.si_claims")}
              value={summary.source_intelligence_claims}
              tone="primary"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.real_support_deficit")}
              value={summary.real_support_deficit_tensions}
              tone="warning"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.real_conflict")}
              value={summary.real_conflict_tensions}
              tone="warning"
              hover={false}
            />
            <MetricCard
              label={t("epistemic_health.metric.real_open")}
              value={summary.real_open_tensions}
              tone="info"
              hover={false}
              helper={t("epistemic_health.metric.real_open_help")}
            />
            <MetricCard
              label={t("epistemic_health.metric.memory_version")}
              value={summary.memory_version}
              tone="primary"
              hover={false}
            />
          </MetricGrid>

          <SectionCard
            title={t("epistemic_health.test_section.title")}
            subtitle={t("epistemic_health.test_section.subtitle")}
          >
            <MetricGrid columns={4}>
              <MetricCard
                label={t("epistemic_health.metric.test_claims")}
                value={summary.test_claims}
                tone="neutral"
                hover={false}
              />
              <MetricCard
                label={t("epistemic_health.metric.test_observations")}
                value={summary.test_observations}
                tone="neutral"
                hover={false}
              />
              <MetricCard
                label={t("epistemic_health.metric.test_evidence")}
                value={summary.test_evidence_links}
                tone="neutral"
                hover={false}
              />
              <MetricCard
                label={t("epistemic_health.metric.test_open")}
                value={summary.test_open_tensions}
                tone="neutral"
                hover={false}
              />
            </MetricGrid>
          </SectionCard>
        </>
      ) : null}

      <FilterBar>
        <span className="ds-text-secondary" style={{ fontSize: "0.85rem" }}>
          {t("epistemic_health.provenance.label")}
        </span>
        {(
          [
            ["real", "epistemic_health.provenance.real"],
            ["test", "epistemic_health.provenance.test"],
            ["all", "epistemic_health.provenance.all"],
          ] as const
        ).map(([value, key]) => (
          <Button
            key={value}
            variant={provenanceScope === value ? "primary" : "secondary"}
            size="sm"
            onClick={() => onProvenanceChange(value)}
          >
            {t(key)}
          </Button>
        ))}
      </FilterBar>

      <FilterBar>
        <span className="ds-text-secondary" style={{ fontSize: "0.85rem" }}>
          {t("epistemic_health.filter.label")}
        </span>
        <Button
          variant={filter === "all" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("all")}
        >
          {t("epistemic_health.filter.all")}
        </Button>
        <Button
          variant={filter === "support_deficit" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("support_deficit")}
        >
          {t("epistemic_health.filter.support_deficit")}
        </Button>
        <Button
          variant={filter === "conflict" ? "primary" : "secondary"}
          size="sm"
          onClick={() => onFilterChange("conflict")}
        >
          {t("epistemic_health.filter.conflict")}
        </Button>
        {!loading ? (
          <Tag>
            {t("epistemic_health.metric.page_help", {
              shown: paged.items.length,
              filtered: filtered.length,
              total: counts.total,
            })}
          </Tag>
        ) : null}
      </FilterBar>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {copyStatus ? <Alert variant="info">{copyStatus}</Alert> : null}

      {viewState === "loading" ? (
        <LoadingState label={t("epistemic_health.loading")} />
      ) : viewState === "error" ? (
        <SectionCard title={t("epistemic_health.empty_title")}>
          <p>{t("epistemic_health.error_load")}</p>
        </SectionCard>
      ) : viewState === "empty" ? (
        <SectionCard title={t("epistemic_health.empty_title")}>
          <p>
            {emptyIsRealOnly
              ? t("epistemic_health.empty_real_only_test")
              : provenanceScope === "real"
                ? t("epistemic_health.empty_real")
                : t("epistemic_health.empty")}
          </p>
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
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <StatusBadge
                      variant={item.tension_type === "conflict" ? "warning" : "neutral"}
                      label={typeLabel(item.tension_type)}
                    />
                    {item.is_test_data ? (
                      <StatusBadge
                        variant="processing"
                        label={t("epistemic_health.provenance.test")}
                      />
                    ) : (
                      <StatusBadge
                        variant="ready"
                        label={t("epistemic_health.provenance.real")}
                      />
                    )}
                  </div>
                }
              >
                <p className="ds-text-secondary" style={{ marginTop: 0 }}>
                  {item.summary}
                </p>
                <dl className="ds-kv-grid">
                  <div className="ds-kv-grid__row">
                    <dt>{t("epistemic_health.col.claims")}</dt>
                    <dd className="ds-kv-grid__mono">{formatIdList(item.claim_ids)}</dd>
                  </div>
                  <div className="ds-kv-grid__row">
                    <dt>{t("epistemic_health.col.observations")}</dt>
                    <dd className="ds-kv-grid__mono">
                      {formatIdList(item.observation_ref_ids)}
                    </dd>
                  </div>
                  <div className="ds-kv-grid__row">
                    <dt>{t("epistemic_health.col.evidence")}</dt>
                    <dd className="ds-kv-grid__mono">
                      {formatIdList(item.evidence_link_ids)}
                    </dd>
                  </div>
                  <div className="ds-kv-grid__row">
                    <dt>{t("epistemic_health.col.provenance_kinds")}</dt>
                    <dd className="ds-kv-grid__mono">
                      {(item.claim_provenance_kinds ?? []).join(", ") || "—"}
                    </dd>
                  </div>
                </dl>

                <Button
                  variant="ghost"
                  size="sm"
                  aria-expanded={open}
                  onClick={() => setExpandedKey(open ? null : key)}
                >
                  <ChevronDown
                    size={14}
                    style={{ transform: open ? "rotate(180deg)" : undefined }}
                  />
                  {open ? t("epistemic_health.collapse") : t("epistemic_health.expand")}
                </Button>

                {open ? (
                  <div className="ds-stack" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
                    <p>
                      <strong>{t("epistemic_health.detail.summary")}</strong>
                      <br />
                      {item.summary}
                    </p>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <strong>{t("epistemic_health.detail.json")}</strong>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void onCopyJson(item)}
                      >
                        {t("epistemic_health.copy_json")}
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
              infoLabel={t("common.page_of", {
                page: paged.page,
                total: paged.totalPages,
              })}
            />
          ) : null}
        </div>
      )}

      <CapabilityMaturitySection />
      <ArchitectureStatusVisual build={build} />
    </PageLayout>
  );
}
