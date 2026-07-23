import { useState } from "react";
import type { Settings } from "../../types";
import { buildIndexingDocHints } from "../../lib/indexingDocs";
import { SectionCard } from "../../ui";

type Props = {
  settings: Settings;
  t: (key: string) => string;
};

type Section = { id: string; titleKey: string; bodyKeys: string[] };

const SECTIONS: Section[] = [
  {
    id: "how",
    titleKey: "indexing.help.section.how",
    bodyKeys: ["indexing.docs.what", "indexing.docs.modes", "indexing.docs.after"],
  },
  {
    id: "internal",
    titleKey: "indexing.help.section.internal",
    bodyKeys: ["indexing.docs.process", "indexing.docs.skip"],
  },
  {
    id: "advanced",
    titleKey: "indexing.help.section.advanced",
    bodyKeys: ["indexing.docs.max_pages", "indexing.docs.scan_all", "indexing.docs.reindex"],
  },
  {
    id: "intelligence",
    titleKey: "indexing.help.section.intelligence",
    bodyKeys: [
      "indexing.docs.intelligence_what",
      "indexing.docs.intelligence_when",
      "indexing.docs.intelligence_actions",
      "indexing.docs.intelligence_estimate",
      "indexing.docs.intelligence_stats",
    ],
  },
  {
    id: "tips",
    titleKey: "indexing.help.section.tips",
    bodyKeys: ["indexing.help.step4", "indexing.help.step5", "indexing.help.limit_hint"],
  },
  {
    id: "troubleshooting",
    titleKey: "indexing.help.section.troubleshooting",
    bodyKeys: ["indexing.docs.debug", "indexing.next.check_errors"],
  },
];

export default function IndexingHelpAccordion({ settings, t }: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const hints = buildIndexingDocHints(settings, t);

  return (
    <SectionCard title={t("indexing.docs.title")}>
      <p className="ds-caption">{t("indexing.docs.collapsed_intro")}</p>
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
                <>
                  <ul className="ds-index-help__body">
                    {section.bodyKeys.map((key) => (
                      <li key={key}>{t(key)}</li>
                    ))}
                  </ul>
                  {section.id === "advanced" && (
                    <p className="ds-caption ds-index-help__hints">
                      {t("indexing.docs.current_settings")}: {hints.join(" · ")}
                    </p>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
