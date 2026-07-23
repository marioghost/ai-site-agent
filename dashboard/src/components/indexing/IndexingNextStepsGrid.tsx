import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  BookOpen,
  Database,
  MessageSquare,
} from "lucide-react";
import type { IndexStatusViewModel } from "../../lib/indexStatus";
import { SectionCard } from "../../ui";

type Props = {
  live: IndexStatusViewModel;
  t: (key: string) => string;
};

type StepCard = {
  id: string;
  to: string;
  icon: ReactNode;
  title: string;
  desc: string;
  show: boolean;
};

export default function IndexingNextStepsGrid({ live, t }: Props) {
  const done = ["completed", "stopped", "failed"].includes(live.jobStatus);
  if (!done) return null;

  const cards: StepCard[] = [
    {
      id: "sources",
      to: "/sources",
      icon: <Database size={22} />,
      title: t("indexing.steps.sources_title"),
      desc: t("indexing.steps.sources_desc"),
      show: true,
    },
    {
      id: "chat",
      to: "/chat",
      icon: <MessageSquare size={22} />,
      title: t("indexing.steps.chat_title"),
      desc: t("indexing.steps.chat_desc"),
      show: live.summary.added + live.summary.updated > 0,
    },
    {
      id: "profile",
      to: "/knowledge-profile",
      icon: <BookOpen size={22} />,
      title: t("indexing.steps.profile_title"),
      desc: t("indexing.steps.profile_desc"),
      show: live.summary.added + live.summary.updated > 0,
    },
    {
      id: "errors",
      to: "/sources?bucket=failed",
      icon: <AlertCircle size={22} />,
      title: t("indexing.steps.errors_title"),
      desc: t("indexing.steps.errors_desc"),
      show: live.summary.errors > 0,
    },
  ].filter((c) => c.show);

  if (cards.length === 0) return null;

  return (
    <SectionCard title={t("indexing.next.title")}>
      <div className="ds-index-steps">
        {cards.map((card) => (
          <Link key={card.id} to={card.to} className="ds-index-step-card">
            <span className="ds-index-step-card__icon">{card.icon}</span>
            <strong className="ds-index-step-card__title">{card.title}</strong>
            <span className="ds-index-step-card__desc">{card.desc}</span>
          </Link>
        ))}
      </div>
    </SectionCard>
  );
}
