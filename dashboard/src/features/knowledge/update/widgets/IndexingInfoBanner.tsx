import { BookOpen } from "lucide-react";

type Props = {
  text: string;
  docLabel: string;
  docHref?: string;
};

export default function IndexingInfoBanner({ text, docLabel, docHref = "#indexing-help" }: Props) {
  return (
    <div className="ds-index-info ds-alert ds-alert--info">
      <div className="ds-index-info__inner">
        <span className="ds-index-info__icon" aria-hidden>
          <BookOpen size={20} />
        </span>
        <p className="ds-index-info__text">{text}</p>
        <a className="ds-index-info__link" href={docHref}>
          {docLabel}
        </a>
      </div>
    </div>
  );
}
