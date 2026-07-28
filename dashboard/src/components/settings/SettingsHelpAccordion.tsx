import { useState } from "react";
import { SectionCard } from "../../ui";

type Section = { id: string; titleKey: string; bodyKeys: string[] };

const SECTIONS: Section[] = [
  {
    id: "intro",
    titleKey: "settings.docs.section.intro",
    bodyKeys: ["settings.docs.intro.simple", "settings.docs.intro.p2"],
  },
  {
    id: "models",
    titleKey: "settings.docs.section.models",
    bodyKeys: [
      "settings.docs.models.llm",
      "settings.docs.models.embedding",
      "settings.docs.models.qdrant",
    ],
  },
  {
    id: "chunking",
    titleKey: "settings.docs.section.chunking",
    bodyKeys: [
      "settings.docs.chunking.size",
      "settings.docs.chunking.overlap",
      "settings.docs.chunking.top_k",
      "settings.docs.chunking.threshold",
    ],
  },
  {
    id: "generation",
    titleKey: "settings.docs.section.generation",
    bodyKeys: [
      "settings.docs.generation.temperature",
      "settings.docs.generation.max_tokens",
      "settings.docs.generation.system_prompt",
      "settings.docs.generation.fallback",
    ],
  },
  {
    id: "retrieval_engine",
    titleKey: "settings.docs.section.retrieval_engine",
    bodyKeys: [
      "settings.docs.retrieval_engine.p1",
      "settings.docs.retrieval_engine.p2",
      "settings.docs.retrieval_engine.p3",
    ],
  },
  {
    id: "retrieval",
    titleKey: "settings.docs.section.retrieval",
    bodyKeys: [
      "settings.docs.retrieval.mode",
      "settings.docs.retrieval.intent",
      "settings.docs.retrieval.context",
      "settings.docs.retrieval.reindex",
    ],
  },
  {
    id: "intelligence",
    titleKey: "settings.docs.section.intelligence",
    bodyKeys: [
      "settings.docs.intelligence.what",
      "settings.docs.intelligence.routing",
      "settings.docs.intelligence.llm",
      "settings.docs.intelligence.workers",
      "settings.docs.intelligence.inline",
      "settings.docs.intelligence.threshold",
    ],
  },
  {
    id: "answer",
    titleKey: "settings.docs.section.answer",
    bodyKeys: [
      "settings.docs.answer.language",
      "settings.docs.answer.mode_profile",
      "settings.docs.answer.context_limits",
      "settings.docs.answer.polish",
      "settings.docs.answer.reranking",
    ],
  },
  {
    id: "cache",
    titleKey: "settings.docs.section.cache",
    bodyKeys: [
      "settings.docs.cache.retrieval",
      "settings.docs.cache.answer",
      "settings.docs.cache.clear",
    ],
  },
  {
    id: "tracing",
    titleKey: "settings.docs.section.tracing",
    bodyKeys: ["settings.docs.tracing.what", "settings.docs.tracing.debug"],
  },
  {
    id: "limits",
    titleKey: "settings.docs.section.limits",
    bodyKeys: [
      "settings.docs.limits.concurrency",
      "settings.docs.limits.timeouts",
    ],
  },
];

type Props = {
  t: (key: string) => string;
};

export default function SettingsHelpAccordion({ t }: Props) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <SectionCard title={t("settings.docs.title")} subtitle={t("settings.docs.subtitle")}>
      <p className="ds-caption">{t("settings.docs.collapsed_intro")}</p>
      <div className="ds-index-help">
        {SECTIONS.map((section) => {
          const open = openId === section.id;
          return (
            <div key={section.id} className="ds-index-help__section">
              <button
                type="button"
                className="ds-index-help__toggle"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : section.id)}
              >
                {t(section.titleKey)}
                <span aria-hidden>{open ? "−" : "+"}</span>
              </button>
              {open && (
                <ul className="ds-index-help__body">
                  {section.bodyKeys.map((key) => (
                    <li key={key}>{t(key)}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
