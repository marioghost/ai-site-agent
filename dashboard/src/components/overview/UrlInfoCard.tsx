import { IconExternal, IconGlobe, IconSitemap } from "./icons";

interface Props {
  label: string;
  url: string | null | undefined;
  emptyLabel: string;
  kind: "site" | "sitemap";
}

export default function UrlInfoCard({ label, url, emptyLabel, kind }: Props) {
  const Icon = kind === "site" ? IconGlobe : IconSitemap;
  const hasUrl = Boolean(url?.trim());

  return (
    <article className="overview-card overview-card--url">
      <div className="overview-card__icon-wrap overview-card__icon-wrap--soft">
        <Icon size={18} />
      </div>
      <div className="overview-card__body">
        <span className="overview-card__label">{label}</span>
        {hasUrl ? (
          <a
            className="overview-url"
            href={url!}
            target="_blank"
            rel="noopener noreferrer"
            title={url!}
          >
            <span className="overview-url__text">{url}</span>
            <IconExternal size={14} className="overview-url__icon" />
          </a>
        ) : (
          <span className="overview-card__value overview-card__value--muted">{emptyLabel}</span>
        )}
      </div>
    </article>
  );
}
