import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, HelpText } from "../../../../ui";

type Props = {
  running: boolean;
  busy: boolean;
  intelligenceRunning?: boolean;
  intelligenceMode?: "generate" | "preview" | null;
  message: string | null;
  onStart: () => void;
  onStop: () => void;
  onReindexAll: () => void;
  onReprocess: () => void;
  onGenerateIntelligence: () => void;
  onReprocessPreview: () => void;
  onIntelligencePreview: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export default function IndexingActionsBar({
  running,
  busy,
  intelligenceRunning = false,
  intelligenceMode = null,
  message,
  onStart,
  onStop,
  onReindexAll,
  onReprocess,
  onGenerateIntelligence,
  onReprocessPreview,
  onIntelligencePreview,
  t,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (intelligenceRunning && intelligenceMode === "preview") {
      setAdvancedOpen(true);
    }
  }, [intelligenceRunning, intelligenceMode]);

  const generateLabel =
    intelligenceRunning && intelligenceMode === "generate"
      ? t("indexing.actions.intelligence_running_short")
      : t("indexing.actions.intelligence");

  const previewLabel =
    intelligenceRunning && intelligenceMode === "preview"
      ? t("indexing.actions.intelligence_preview_running_short")
      : t("indexing.actions.intelligence_preview");

  return (
    <div className="ds-index-actions">
      <div className="ds-index-actions__primary">
        <Button onClick={onStart} disabled={running || busy}>
          {t("indexing.run.start")}
        </Button>
        <Button variant="danger" onClick={onStop} disabled={!running && !intelligenceRunning}>
          {t("indexing.run.stop")}
        </Button>
        <Button variant="secondary" onClick={onReindexAll} disabled={running || busy}>
          {t("indexing.run.reindex_all")}
        </Button>
        <Button variant="secondary" onClick={onReprocess} disabled={running || busy}>
          {t("indexing.actions.reprocess")}
        </Button>
        <Button
          variant="secondary"
          onClick={onGenerateIntelligence}
          disabled={running || busy}
          aria-busy={intelligenceRunning && intelligenceMode === "generate"}
          className={
            intelligenceRunning && intelligenceMode === "generate"
              ? "ds-index-actions__intel-btn ds-index-actions__intel-btn--active"
              : undefined
          }
        >
          {generateLabel}
        </Button>
      </div>
      <button
        type="button"
        className="ds-index-actions__advanced-toggle"
        onClick={() => setAdvancedOpen((v) => !v)}
        aria-expanded={advancedOpen}
      >
        {t("indexing.actions.advanced")}
        {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {advancedOpen && (
        <div className="ds-index-actions__advanced">
          <Button variant="ghost" size="sm" onClick={onReprocessPreview} disabled={running || busy}>
            {t("indexing.actions.reprocess_preview")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onIntelligencePreview}
            disabled={running || busy}
            aria-busy={intelligenceRunning && intelligenceMode === "preview"}
            className={
              intelligenceRunning && intelligenceMode === "preview"
                ? "ds-index-actions__intel-btn ds-index-actions__intel-btn--active"
                : undefined
            }
          >
            {previewLabel}
          </Button>
        </div>
      )}
      {message && <HelpText>{message}</HelpText>}
    </div>
  );
}
