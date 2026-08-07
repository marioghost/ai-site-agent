/**
 * S006 (G7-P5) — Engineering Advanced controls.
 *
 * Product Answers owns answer-quality modes (retrieval_profile).
 * This panel exposes eng overrides + infra knobs only — no dual preset picker,
 * no generation knobs that Answers/llm_mode_profile already own.
 */
import type { Settings } from "../../../../types";
import RetrievalEnginePanel from "./RetrievalEnginePanel";
import {
  Button,
  CheckboxField,
  Field,
  FormGrid,
  FormStack,
  HelpText,
  Input,
  SectionCard,
  Select,
  Textarea,
} from "../../../../ui";

type Props = {
  settings: Settings;
  onChange: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  onClearCache: (kind: "retrieval" | "answer" | "all") => void;
  cacheBusy: string | null;
};

export default function SettingsAdvancedSection({
  settings,
  onChange,
  t,
  onClearCache,
  cacheBusy,
}: Props) {
  return (
    <SectionCard title={t("settings.advanced.title")} subtitle={t("settings.advanced.subtitle")}>
      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.chunking.title")}</h4>
        <FormGrid columns={4}>
          <Field label={t("settings.chunking.size")}>
            <Input
              type="number"
              value={settings.chunk_size}
              onChange={(e) => onChange("chunk_size", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.chunking.overlap")}>
            <Input
              type="number"
              value={settings.chunk_overlap}
              onChange={(e) => onChange("chunk_overlap", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.chunking.threshold")}>
            <Input
              type="number"
              step="0.01"
              value={settings.similarity_threshold}
              onChange={(e) => onChange("similarity_threshold", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.models.qdrant")}>
            <Input
              value={settings.qdrant_collection}
              onChange={(e) => onChange("qdrant_collection", e.target.value)}
            />
          </Field>
        </FormGrid>
        <HelpText>{t("settings.retrieval.reindex_hint")}</HelpText>
      </div>

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.retrieval.title")}</h4>
        <HelpText>{t("settings.retrieval.help")}</HelpText>
        <FormGrid columns={1}>
          <Field label={t("settings.retrieval.mode")}>
            <Select
              value={settings.retrieval_mode}
              onChange={(e) =>
                onChange("retrieval_mode", e.target.value as Settings["retrieval_mode"])
              }
            >
              <option value="hybrid">{t("settings.retrieval.mode.hybrid")}</option>
              <option value="dense">{t("settings.retrieval.mode.dense")}</option>
              <option value="lexical">{t("settings.retrieval.mode.lexical")}</option>
            </Select>
          </Field>
        </FormGrid>
        <FormGrid columns={3}>
          <Field label={t("settings.retrieval.candidate_count")}>
            <Input
              type="number"
              value={settings.retrieval_candidate_count}
              onChange={(e) => onChange("retrieval_candidate_count", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.retrieval.max_pages")}>
            <Input
              type="number"
              value={settings.max_pages_in_context}
              onChange={(e) => onChange("max_pages_in_context", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.retrieval.max_chunks_page")}>
            <Input
              type="number"
              value={settings.max_chunks_per_page}
              onChange={(e) => onChange("max_chunks_per_page", Number(e.target.value))}
            />
          </Field>
        </FormGrid>
        <HelpText>{t("eng.advanced.generation_owned_by_answers")}</HelpText>
      </div>

      <RetrievalEnginePanel settings={settings} onChange={onChange} t={t} />

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.intelligence.title")}</h4>
        <FormStack>
          <CheckboxField
            label={t("settings.intelligence.llm_profiles")}
            checked={settings.enable_llm_source_intelligence ?? true}
            onChange={(e) => onChange("enable_llm_source_intelligence", e.target.checked)}
          />
          <Field label={t("settings.intelligence.worker_count")}>
            <Select
              value={String(settings.source_intelligence_worker_count ?? 0)}
              onChange={(e) =>
                onChange("source_intelligence_worker_count", Number(e.target.value))
              }
            >
              <option value="0">{t("settings.intelligence.worker_auto")}</option>
              <option value="1">{t("settings.intelligence.worker_one")}</option>
              <option value="2">{t("settings.intelligence.worker_two")}</option>
            </Select>
          </Field>
          <CheckboxField
            label={t("settings.intelligence.inline_indexing")}
            checked={settings.run_source_intelligence_inline_during_indexing ?? false}
            onChange={(e) =>
              onChange("run_source_intelligence_inline_during_indexing", e.target.checked)
            }
          />
        </FormStack>
      </div>

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.cache.title")}</h4>
        <FormStack>
          <CheckboxField
            label={t("settings.cache.retrieval")}
            checked={settings.enable_retrieval_cache}
            onChange={(e) => onChange("enable_retrieval_cache", e.target.checked)}
          />
          <CheckboxField
            label={t("settings.cache.answer")}
            checked={settings.enable_semantic_answer_cache}
            onChange={(e) => onChange("enable_semantic_answer_cache", e.target.checked)}
          />
        </FormStack>
        <FormGrid columns={2}>
          <Field label={t("settings.cache.retrieval_ttl")}>
            <Input
              type="number"
              value={settings.retrieval_cache_ttl_seconds}
              onChange={(e) => onChange("retrieval_cache_ttl_seconds", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.cache.answer_ttl")}>
            <Input
              type="number"
              value={settings.answer_cache_ttl_seconds}
              onChange={(e) => onChange("answer_cache_ttl_seconds", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.cache.similarity")}>
            <Input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={settings.semantic_cache_similarity_threshold}
              onChange={(e) =>
                onChange("semantic_cache_similarity_threshold", Number(e.target.value))
              }
            />
          </Field>
          <Field label={t("settings.cache.max_answers")}>
            <Input
              type="number"
              min={0}
              value={settings.max_cached_answers}
              onChange={(e) => onChange("max_cached_answers", Number(e.target.value))}
            />
          </Field>
        </FormGrid>
        <div className="ds-settings-advanced__actions">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!!cacheBusy}
            onClick={() => onClearCache("retrieval")}
          >
            {t("settings.cache.clear_retrieval")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!!cacheBusy}
            onClick={() => onClearCache("answer")}
          >
            {t("settings.cache.clear_answer")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!!cacheBusy}
            onClick={() => onClearCache("all")}
          >
            {t("settings.cache.clear_all")}
          </Button>
        </div>
      </div>

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.tracing.title")}</h4>
        <FormStack>
          <CheckboxField
            label={t("settings.tracing.enable")}
            checked={settings.enable_tracing}
            onChange={(e) => onChange("enable_tracing", e.target.checked)}
          />
          <CheckboxField
            label={t("settings.tracing.debug_payload")}
            checked={settings.enable_chat_debug_payload}
            onChange={(e) => onChange("enable_chat_debug_payload", e.target.checked)}
          />
          <CheckboxField
            label={t("settings.tracing.semantic_diagnostics_v2")}
            checked={settings.enable_semantic_diagnostics_v2 ?? false}
            onChange={(e) => onChange("enable_semantic_diagnostics_v2", e.target.checked)}
          />
        </FormStack>
      </div>

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.limits.title")}</h4>
        <FormGrid columns={3}>
          <Field label={t("settings.limits.max_chat")}>
            <Input
              type="number"
              value={settings.max_concurrent_chat_requests}
              onChange={(e) => onChange("max_concurrent_chat_requests", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.limits.chat_timeout")}>
            <Input
              type="number"
              value={settings.chat_total_timeout_seconds}
              onChange={(e) => onChange("chat_total_timeout_seconds", Number(e.target.value))}
            />
          </Field>
          <Field label={t("settings.limits.gen_timeout")}>
            <Input
              type="number"
              value={settings.ollama_generation_timeout_seconds}
              onChange={(e) =>
                onChange("ollama_generation_timeout_seconds", Number(e.target.value))
              }
            />
          </Field>
        </FormGrid>
      </div>

      <div className="ds-settings-advanced__block">
        <h4 className="ds-settings-advanced__heading">{t("settings.generation.system_prompt")}</h4>
        <p className="ds-settings-advanced__hint">{t("settings.docs.generation.system_prompt")}</p>
        <Textarea
          rows={10}
          value={settings.system_prompt}
          onChange={(e) => onChange("system_prompt", e.target.value)}
        />
      </div>
    </SectionCard>
  );
}
