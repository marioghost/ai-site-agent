import { SectionCard, StatusBadge } from "../../ui";

type Props = {
  entries: { time: string; level: string; message: string }[];
  t: (key: string) => string;
};

function levelVariant(level: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (level === "error") return "danger";
  if (level === "warning") return "warning";
  if (level === "success" || level === "ok") return "success";
  if (level === "info") return "info";
  return "neutral";
}

function levelLabel(level: string, t: (key: string) => string): string {
  const key = `indexing.activity.level.${level}`;
  const translated = t(key);
  return translated !== key ? translated : level;
}

export default function IndexingActivitySection({ entries, t }: Props) {
  const items = entries.slice(0, 30);

  return (
    <SectionCard title={t("indexing.activity.title")}>
      {items.length === 0 ? (
        <p className="ds-caption">{t("indexing.activity.empty")}</p>
      ) : (
        <div className="ds-index-timeline">
          {items.map((entry, i) => (
            <div
              key={`${entry.time}-${i}`}
              className={`ds-index-timeline__row ds-index-timeline__row--${entry.level ?? "info"}`}
            >
              <time className="ds-index-timeline__time">{entry.time}</time>
              <StatusBadge
                variant={levelVariant(entry.level ?? "info")}
                label={levelLabel(entry.level ?? "info", t)}
              />
              <span className="ds-index-timeline__msg">{entry.message}</span>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
