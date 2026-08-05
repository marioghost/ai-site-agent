import { useEffect, useMemo, useRef, useState } from "react";
import {
  applyGeneratedKnowledgeProfile,
  getKnowledgeProfileGenerationStatus,
  startKnowledgeProfileGeneration,
} from "../../../../api/client";
import type { ConfidenceItem, GenerationPreview, KnowledgeProfile } from "../../../../types";
import { useTranslation } from "../../../../i18n";
import {
  Alert,
  Button,
  CheckboxField,
  LoadingState,
  Modal,
  StatusBadge,
} from "../../../../ui";
import KnowledgeProfileLegacyBanner from "./KnowledgeProfileLegacyBanner";

type Props = {
  onApplied: (profile: KnowledgeProfile) => void;
  onClose: () => void;
};

const STAGE_ORDER = [
  "metadata_extraction",
  "website_analysis",
  "statistics",
  "entity_extraction",
  "organization_detection",
  "topic_discovery",
  "content_hint_discovery",
  "knowledge_graph",
  "profile_assembly",
  "llm_refinement",
  "validation",
  "auto_repair",
  "preview",
  "complete",
] as const;

function confidenceVariant(c: number): "ready" | "pending" | "failed" {
  if (c >= 0.75) return "ready";
  if (c >= 0.5) return "pending";
  return "failed";
}

function stageLabel(stage: string, t: (k: string) => string): string {
  const key = `knowledge_profile.generate.stage.${stage}`;
  const translated = t(key as "knowledge_profile.generate.stage.metadata_extraction");
  return translated === key ? stage.replace(/_/g, " ") : translated;
}

function summarizeWarnings(warnings: string[]): string[] {
  const duplicateAliases: string[] = [];
  const rest: string[] = [];

  for (const warning of warnings) {
    const match = warning.match(/Duplicate alias '([^']+)'/);
    if (match) {
      duplicateAliases.push(match[1]);
      continue;
    }
    rest.push(warning);
  }

  const summarized = [...rest];
  if (duplicateAliases.length > 0) {
    const unique = [...new Set(duplicateAliases)];
    summarized.push(
      unique.length <= 4
        ? `Duplicate aliases removed: ${unique.join(", ")}`
        : `Duplicate aliases removed (${unique.length}): ${unique.slice(0, 4).join(", ")}…`
    );
  }
  return summarized;
}

export default function KnowledgeProfileGenerateWizard({ onApplied, onClose }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string>("idle");
  const [stage, setStage] = useState("");
  const [progress, setProgress] = useState(0);
  const [preview, setPreview] = useState<GenerationPreview | null>(null);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mergeIdentity, setMergeIdentity] = useState(false);
  const [useLlm, setUseLlm] = useState(true);
  const timer = useRef<number | null>(null);

  const stageIndex = useMemo(
    () => STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number]),
    [stage]
  );

  const running = busy || status === "running";
  const summarizedWarnings = useMemo(
    () => summarizeWarnings(preview?.warnings ?? []),
    [preview?.warnings]
  );

  const poll = async () => {
    try {
      const data = await getKnowledgeProfileGenerationStatus();
      setStatus(data.status);
      setStage(data.current_stage || "");
      setProgress(data.progress_percent || 0);
      if (data.preview) setPreview(data.preview);
      if (data.analytics) setAnalytics(data.analytics);
      if (data.status === "failed" && data.error_message) {
        setError(data.error_message);
      } else if (data.status === "completed") {
        setError(null);
      }
      if (data.status === "completed" || data.status === "failed") {
        if (timer.current) window.clearInterval(timer.current);
        setBusy(false);
      }
    } catch {
      /* ignore transient poll errors */
    }
  };

  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current);
    },
    []
  );

  const onGenerate = async () => {
    setBusy(true);
    setError(null);
    setPreview(null);
    setAnalytics(null);
    try {
      await startKnowledgeProfileGeneration({ use_llm: useLlm, merge_identity: mergeIdentity });
      timer.current = window.setInterval(poll, 1200);
      await poll();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || t("knowledge_profile.generate.error_start"));
      setBusy(false);
    }
  };

  const onApply = async () => {
    if (!preview?.profile) return;
    setBusy(true);
    try {
      const res = await applyGeneratedKnowledgeProfile(preview.profile);
      onApplied(res.profile as KnowledgeProfile);
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string | string[] } } };
      const detail = err?.response?.data?.detail;
      setError(
        Array.isArray(detail) ? detail.join("; ") : detail || t("knowledge_profile.generate.error_apply")
      );
    } finally {
      setBusy(false);
    }
  };

  const showPreview = Boolean(preview && status === "completed");

  return (
    <Modal
      open
      size="xl"
      className="ds-kp-wizard-modal"
      title={t("knowledge_profile.generate.title")}
      subtitle={t("knowledge_profile.generate.subtitle")}
      onClose={onClose}
      actions={
        showPreview ? (
          <>
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              {t("common.cancel")}
            </Button>
            <Button onClick={onApply} disabled={busy}>
              {t("knowledge_profile.generate.apply")}
            </Button>
          </>
        ) : !running ? (
          <>
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              {t("common.cancel")}
            </Button>
            <Button onClick={onGenerate} disabled={busy}>
              {t("knowledge_profile.generate.start")}
            </Button>
          </>
        ) : undefined
      }
    >
      <div className={`ds-kp-wizard${running ? " ds-kp-wizard--running" : ""}`}>
        <div className="ds-kp-wizard__main">
          <KnowledgeProfileLegacyBanner />

          {!showPreview && (
            <div className="ds-kp-wizard__options">
              <CheckboxField
                label={t("knowledge_profile.generate.use_llm")}
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                disabled={running}
              />
              <CheckboxField
                label={t("knowledge_profile.generate.merge_identity")}
                checked={mergeIdentity}
                onChange={(e) => setMergeIdentity(e.target.checked)}
                disabled={running}
              />
            </div>
          )}

          {error ? <Alert variant="error">{error}</Alert> : null}

          {showPreview && preview && (
            <div className="ds-kp-wizard__preview">
              {preview.organization && (
                <div className="ds-kp-wizard__fact">
                  <span className="ds-kp-wizard__fact-label">{t("knowledge_profile.generate.org")}</span>
                  <span className="ds-kp-wizard__fact-value">
                    {preview.organization.value}
                    <StatusBadge
                      variant={confidenceVariant(preview.organization.confidence)}
                      label={`${Math.round(preview.organization.confidence * 100)}%`}
                    />
                  </span>
                </div>
              )}

              {preview.website_type && (
                <div className="ds-kp-wizard__fact">
                  <span className="ds-kp-wizard__fact-label">{t("knowledge_profile.generate.type")}</span>
                  <span className="ds-kp-wizard__fact-value">
                    {preview.website_type.value}
                    <StatusBadge
                      variant={confidenceVariant(preview.website_type.confidence)}
                      label={`${Math.round(preview.website_type.confidence * 100)}%`}
                    />
                  </span>
                </div>
              )}

              {preview.topics.length > 0 && (
                <div className="ds-kp-wizard__block">
                  <h3 className="ds-kp-wizard__block-title">{t("knowledge_profile.generate.topics")}</h3>
                  <ul className="ds-preview-list">
                    {preview.topics.slice(0, 12).map((topic: ConfidenceItem) => (
                      <li key={topic.value}>
                        {topic.value}
                        {topic.page_count
                          ? ` (${topic.page_count} ${t("knowledge_profile.generate.pages")})`
                          : ""}
                        {" — "}
                        {Math.round(topic.confidence * 100)}%
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {preview.content_hints && preview.content_hints.length > 0 && (
                <div className="ds-kp-wizard__block">
                  <h3 className="ds-kp-wizard__block-title">
                    {t("knowledge_profile.generate.content_hints")}
                  </h3>
                  <ul className="ds-preview-list">
                    {preview.content_hints.map((h: ConfidenceItem) => (
                      <li key={h.value}>
                        {h.value} ({h.page_count ?? 0} {t("knowledge_profile.generate.pages")})
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summarizedWarnings.length > 0 && (
                <Alert variant="warning">
                  <ul className="ds-kp-wizard__warnings">
                    {summarizedWarnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </Alert>
              )}

              {preview.low_confidence_keys.length > 0 && (
                <p className="ds-caption">{t("knowledge_profile.generate.review_hint")}</p>
              )}
            </div>
          )}
        </div>

        {running && (
          <aside className="ds-kp-wizard__sidebar">
            <h3 className="ds-kp-wizard__sidebar-title">{t("knowledge_profile.generate.pipeline_title")}</h3>
            <p className="ds-caption">
              {t("knowledge_profile.generate.progress", {
                stage: stageLabel(stage, t),
                progress,
              })}
            </p>
            <div className="ds-kp-wizard__progress">
              <div className="ds-kp-wizard__progress-bar" style={{ width: `${progress}%` }} />
            </div>
            <ol className="ds-kp-stage-list">
              {STAGE_ORDER.slice(0, -1).map((s, i) => (
                <li
                  key={s}
                  className={`ds-kp-stage-list__item${stageIndex >= i ? " ds-kp-stage-list__item--done" : ""}${stage === s ? " ds-kp-stage-list__item--active" : ""}`}
                >
                  {stageLabel(s, t)}
                </li>
              ))}
            </ol>
            {status === "running" && !preview ? (
              <LoadingState label={t("common.processing")} />
            ) : null}
          </aside>
        )}
      </div>

      {showPreview && analytics && (
        <details className="ds-kp-wizard__analytics">
          <summary>{t("knowledge_profile.generate.analytics_title")}</summary>
          <ul className="ds-preview-list">
            {Object.entries(analytics)
              .filter(([k]) => !["validation_issues", "errors", "stage_timings"].includes(k))
              .slice(0, 10)
              .map(([k, v]) => (
                <li key={k}>
                  {k}: {String(v)}
                </li>
              ))}
          </ul>
        </details>
      )}
    </Modal>
  );
}
