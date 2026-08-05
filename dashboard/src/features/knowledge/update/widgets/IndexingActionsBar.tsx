import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { Button, HelpText } from "../../../../ui";

type Props = {
  running: boolean;
  busy: boolean;
  message: string | null;
  onStart: () => void;
  onStop: () => void;
  onReindexAll: () => void;
  onReprocess: () => void;
  onReprocessPreview: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export default function IndexingActionsBar({
  running,
  busy,
  message,
  onStart,
  onStop,
  onReindexAll,
  onReprocess,
  onReprocessPreview,
  t,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <div className="ds-index-actions">
      <div className="ds-index-actions__primary">
        <Button onClick={onStart} disabled={running || busy}>
          {t("indexing.run.start")}
        </Button>
        <Button variant="danger" onClick={onStop} disabled={!running}>
          {t("indexing.run.stop")}
        </Button>
        <Button variant="secondary" onClick={onReindexAll} disabled={running || busy}>
          {t("indexing.run.reindex_all")}
        </Button>
        <Button variant="secondary" onClick={onReprocess} disabled={running || busy}>
          {t("indexing.actions.reprocess")}
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
        </div>
      )}
      {message && <HelpText>{message}</HelpText>}
    </div>
  );
}
