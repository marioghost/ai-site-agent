import {
  AlertCircle,
  Ban,
  Check,
  Clock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import type { IndexQueuePreviewViewModel, IndexStatusViewModel } from "../../../../lib/indexStatus";
import { MetricGrid, SectionCard } from "../../../../ui";
import SourceSummaryCard from "../../shared/SourceSummaryCard";

type Props = {
  queue: IndexQueuePreviewViewModel;
  live: IndexStatusViewModel;
  lang: string;
  t: (key: string) => string;
};

function fmt(n: number, lang: string) {
  return n.toLocaleString(lang === "uk" ? "uk-UA" : "en-US");
}

export default function IndexingQueueCard({ queue, lang, t }: Props) {
  return (
    <SectionCard title={t("indexing.next_queue.title")} subtitle={t("indexing.queue.subtitle_short")}>
      <MetricGrid columns={6}>
        <SourceSummaryCard
          tone="purple"
          icon={<Sparkles size={18} />}
          label={t("indexing.queue.ready")}
          value={fmt(queue.newPagesWaiting, lang)}
          helper={t("indexing.queue.ready_help")}
        />
        <SourceSummaryCard
          tone="orange"
          icon={<Clock size={18} />}
          label={t("indexing.queue.waiting")}
          value={fmt(queue.queuedForRun || queue.totalWaiting, lang)}
          helper={t("indexing.queue.waiting_help")}
        />
        <SourceSummaryCard
          tone="green"
          icon={<Check size={18} />}
          label={t("indexing.queue.indexed")}
          value={fmt(queue.freshSkipped, lang)}
          helper={t("indexing.queue.indexed_help")}
        />
        <SourceSummaryCard
          tone="blue"
          icon={<RefreshCw size={18} />}
          label={t("indexing.queue.refresh")}
          value={fmt(queue.stalePagesWaiting, lang)}
          helper={t("indexing.queue.refresh_help")}
        />
        <SourceSummaryCard
          tone="pink"
          icon={<AlertCircle size={18} />}
          label={t("indexing.queue.failed")}
          value={fmt(queue.failedPagesWaiting, lang)}
          helper={t("indexing.queue.failed_help")}
        />
        <SourceSummaryCard
          tone="neutral"
          icon={<Ban size={18} />}
          label={t("indexing.queue.skipped_kpi")}
          value={fmt(queue.skippedPagesWaiting, lang)}
          helper={t("indexing.queue.skipped_help")}
        />
      </MetricGrid>
    </SectionCard>
  );
}
