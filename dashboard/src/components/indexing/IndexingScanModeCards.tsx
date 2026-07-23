import type { ScanMode, Settings } from "../../types";

const MODES: ScanMode[] = ["pages_only", "pages_and_files", "files_only"];

type Props = {
  settings: Settings;
  onChange: (mode: ScanMode) => void;
  t: (key: string) => string;
};

export default function IndexingScanModeCards({ settings, onChange, t }: Props) {
  return (
    <div className="ds-scan-modes" role="radiogroup" aria-label={t("indexing.what_to_scan")}>
      {MODES.map((mode) => {
        const active = settings.scan_mode === mode;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={active}
            className={`ds-scan-mode${active ? " ds-scan-mode--active" : ""}`}
            onClick={() => onChange(mode)}
          >
            <strong>{t(`indexing.scan_mode.${mode}.title`)}</strong>
            <span className="ds-caption">{t(`indexing.scan_mode.${mode}.desc`)}</span>
          </button>
        );
      })}
    </div>
  );
}
