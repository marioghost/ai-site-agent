import { useCallback, useEffect, useMemo, useState } from "react";
import { getBuildInfo, getHealth, getIndexStatus } from "../../../api/client";
import SubsystemHealthPanel, {
  type SubsystemGroup,
  type SubsystemItem,
} from "../../../components/overview/SubsystemHealthPanel";
import {
  IconBrain,
  IconCube,
  IconDatabase,
  IconServer,
  IconSync,
} from "../../../components/overview/icons";
import LlmRuntimePanel from "../../../components/settings/LlmRuntimePanel";
import { useTranslation } from "../../../i18n";
import { Alert, Button, ErrorState, LoadingState, PageHeader, PageLayout, Tag } from "../../../ui";
import type { BuildInfo, HealthResponse, IndexJobStatus } from "../../../types";

/**
 * S006 — Engineering owner for live subsystem/backend health. Reuses the
 * same `SubsystemHealthPanel` widget as Overview (a shared, non-feature
 * component) with its own `getHealth`/`getIndexStatus`/`getBuildInfo` calls.
 *
 * S007 (G6-P2) — Now also the owner for the retired Overview's Knowledge OS
 * release/version tags and the LLM runtime/benchmark panel (`LlmRuntimePanel`,
 * previously only mounted on `OverviewPage`), completing the redistribution.
 */
export default function EngStatusScreen() {
  const { t, healthStatusLabel, jobStatusLabel } = useTranslation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [job, setJob] = useState<IndexJobStatus | null>(null);
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(false);
    try {
      const [h, j, b] = await Promise.all([getHealth(), getIndexStatus(), getBuildInfo()]);
      setHealth(h);
      setJob(j);
      setBuild(b);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    void load();
  };

  const groups = useMemo((): SubsystemGroup[] => {
    if (!health) return [];
    const items: SubsystemItem[] = [
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
      },
    ];
    return [{ id: "health", title: t("overview.subsystem_group_health"), items }];
  }, [health, job, t, healthStatusLabel, jobStatusLabel]);

  return (
    <PageLayout>
      <PageHeader
        title={t("nav.eng_status")}
        subtitle={t("eng.status.subtitle")}
        actions={
          <Button variant="secondary" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? t("common.processing") : t("common.refresh")}
          </Button>
        }
      />

      {loading && <LoadingState label={t("common.loading")} />}

      {!loading && error && (
        <ErrorState
          title={t("eng.status.error_title")}
          description={t("eng.status.error_description")}
          action={
            <Button variant="secondary" onClick={onRefresh}>
              {t("home.retry")}
            </Button>
          }
        />
      )}

      {!loading && !error && (
        <>
          {build && (
            <Alert variant="info">
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                <Tag>
                  {t("eng.status.release_tag", {
                    release: build.release_status?.accepted ?? build.release,
                  })}
                </Tag>
                {build.release_status?.in_progress ? (
                  <Tag>
                    {t("overview.kos.release_in_progress", {
                      version: build.release_status.in_progress,
                    })}
                  </Tag>
                ) : null}
                <Tag>
                  {t("overview.kos.memory_version")}: {build.memory_version}
                </Tag>
                <Tag>
                  {t("overview.kos.knowledge_version")}: {build.knowledge_version}
                </Tag>
              </div>
            </Alert>
          )}
          <SubsystemHealthPanel title={t("overview.subsystem_details")} groups={groups} />
          <LlmRuntimePanel variant="overview" />
        </>
      )}
    </PageLayout>
  );
}
