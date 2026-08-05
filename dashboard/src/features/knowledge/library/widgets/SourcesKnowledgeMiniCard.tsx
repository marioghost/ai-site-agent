import type { KnowledgeBaseStatus } from "../../../../types";
import { formatCount } from "./sourceUtils";

type Props = {
  data: KnowledgeBaseStatus;
  lang: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export default function SourcesKnowledgeMiniCard({ data, lang, t }: Props) {
  const pct = Math.min(100, Math.max(0, data.readiness_percent));
  const total = data.ready_to_use + data.waiting + data.failed;

  return (
    <aside className="ds-kb-mini ds-kb-mini--floating" aria-label={t("sources.mini_kb.title")}>
      <div className="ds-kb-mini__content">
        <div className="ds-kb-mini__title">{t("sources.mini_kb.title")}</div>
        <div className="ds-kb-mini__percent">
          {t("sources.mini_kb.ready", { percent: pct.toFixed(0) })}
        </div>
        <div className="ds-kb-mini__progress">
          <div className="ds-kb-status__track ds-kb-mini__track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="ds-kb-status__fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="ds-kb-mini__meta">
            {t("sources.mini_kb.progress", {
              ready: formatCount(data.ready_to_use, lang),
              total: formatCount(total, lang),
            })}
          </p>
        </div>
      </div>
    </aside>
  );
}
