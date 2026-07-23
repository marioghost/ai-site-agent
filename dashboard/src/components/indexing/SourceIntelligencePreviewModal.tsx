import { Modal } from "../../ui";
import SourceIntelligencePanel from "../sources/SourceIntelligencePanel";
import { useTranslation } from "../../i18n";
import type { SourceSemanticProfile } from "../../types";

type ProfileSample = {
  url?: string;
  title?: string;
  semantic?: SourceSemanticProfile | Record<string, unknown>;
  llm_summary?: string;
  profile_version?: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
  profiles: ProfileSample[];
  total: number;
};

export default function SourceIntelligencePreviewModal({
  open,
  onClose,
  profiles,
  total,
}: Props) {
  const { t } = useTranslation();

  return (
    <Modal
      open={open}
      title={t("indexing.intelligence.preview_title")}
      subtitle={t("indexing.intelligence.preview_subtitle", { total, shown: profiles.length })}
      onClose={onClose}
      size="xl"
    >
      <div className="ds-intelligence-preview-list">
        {profiles.map((sample, i) => (
          <article key={`${sample.url}-${i}`} className="ds-intelligence-preview-item">
            <header className="ds-intelligence-preview-item__head">
              <h3>{sample.title || sample.url}</h3>
              {sample.url && (
                <a href={sample.url} target="_blank" rel="noreferrer">
                  {sample.url}
                </a>
              )}
            </header>
            <SourceIntelligencePanel
              profile={sample.semantic}
              summary={sample.llm_summary}
              profileVersion={sample.profile_version}
            />
          </article>
        ))}
      </div>
    </Modal>
  );
}
