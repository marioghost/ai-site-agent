import { Download, Trash2, Star } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { deleteOllamaModel, getModels, pullOllamaModel } from "../../api/client";
import { useTranslation } from "../../i18n";
import type { OllamaModel, Settings } from "../../types";
import {
  Alert,
  Button,
  ConfirmDialog,
  HelpText,
  StatusBadge,
} from "../../ui";
import { ollamaModelInstalled } from "../../lib/ollamaModelUtils";

const RECOMMENDED_CHAT_MODELS = [
  "qwen2.5:3b",
  "llama3.2:3b",
  "gemma2:2b",
  "phi3:mini",
  "qwen2.5:7b",
] as const;

function formatBytes(bytes?: number | null): string {
  if (!bytes) return "—";
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  return `${Math.round(bytes / 1024 ** 2)} MB`;
}

type Props = {
  settings: Settings;
  models: OllamaModel[];
  ollamaReachable?: boolean;
  onModelsChange: (models: OllamaModel[]) => void;
  onSelectLlmModel: (model: string) => void;
};

export default function OllamaModelsPanel({
  settings,
  models,
  ollamaReachable = true,
  onModelsChange,
  onSelectLlmModel,
}: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ variant: "success" | "error"; text: string } | null>(
    null
  );
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const modelNames = useMemo(() => models.map((m) => m.name), [models]);
  const llmInstalled = ollamaModelInstalled(settings.llm_model, modelNames);
  const embeddingInstalled = ollamaModelInstalled(settings.embedding_model, modelNames);

  const refreshModels = useCallback(async () => {
    try {
      const res = await getModels();
      onModelsChange(res.models);
      return res.models;
    } catch {
      onModelsChange([]);
      return [];
    }
  }, [onModelsChange]);

  const onPull = async (model: string) => {
    setBusy(`pull:${model}`);
    setMessage(null);
    try {
      const res = await pullOllamaModel(model);
      await refreshModels();
      setMessage({
        variant: "success",
        text: t("settings.models.pull_success", {
          model: res.model,
          duration: Math.round((res.duration_ms || 0) / 1000),
        }),
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage({
        variant: "error",
        text: err?.response?.data?.detail || t("settings.models.pull_error"),
      });
    } finally {
      setBusy(null);
    }
  };

  const onDelete = async (model: string) => {
    setBusy(`delete:${model}`);
    setMessage(null);
    try {
      await deleteOllamaModel(model);
      await refreshModels();
      setMessage({ variant: "success", text: t("settings.models.delete_success", { model }) });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage({
        variant: "error",
        text: err?.response?.data?.detail || t("settings.models.delete_error"),
      });
    } finally {
      setBusy(null);
      setDeleteTarget(null);
    }
  };

  const recommendedToInstall = RECOMMENDED_CHAT_MODELS.filter(
    (name) => !ollamaModelInstalled(name, modelNames)
  );

  return (
    <div className="ds-ollama-models">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}

      {!ollamaReachable && (
        <Alert variant="error">{t("settings.models.ollama_down")}</Alert>
      )}

      {ollamaReachable && !llmInstalled && (
        <div className="ds-ollama-models__missing">
          <div>
            <strong>{t("settings.models.missing_title", { model: settings.llm_model })}</strong>
            <HelpText>{t("settings.models.missing_help")}</HelpText>
          </div>
          <Button
            variant="primary"
            size="sm"
            disabled={busy !== null}
            onClick={() => void onPull(settings.llm_model)}
          >
            <Download size={16} className={busy === `pull:${settings.llm_model}` ? "ds-spin" : undefined} />
            {busy === `pull:${settings.llm_model}`
              ? t("settings.models.pulling")
              : t("settings.models.install")}
          </Button>
        </div>
      )}

      {ollamaReachable && !embeddingInstalled && (
        <Alert variant="warning">
          {t("settings.models.embedding_missing", { model: settings.embedding_model })}
          <Button
            variant="secondary"
            size="sm"
            className="ds-ollama-models__inline-btn"
            disabled={busy !== null}
            onClick={() => void onPull(settings.embedding_model)}
          >
            {t("settings.models.install")}
          </Button>
        </Alert>
      )}

      {recommendedToInstall.length > 0 && (
        <div className="ds-ollama-models__recommended">
          <span className="ds-ollama-models__recommended-label">
            <Star size={14} />
            {t("settings.models.recommended_install")}
          </span>
          <div className="ds-ollama-models__chips">
            {recommendedToInstall.map((name) => (
              <Button
                key={name}
                variant="secondary"
                size="sm"
                disabled={busy !== null}
                onClick={() => void onPull(name)}
              >
                <Download size={14} />
                {busy === `pull:${name}` ? t("settings.models.pulling") : name}
              </Button>
            ))}
          </div>
        </div>
      )}

      {models.length > 0 ? (
        <div className="ds-ollama-models__table-wrap">
          <table className="ds-ollama-models__table">
            <thead>
              <tr>
                <th>{t("settings.models.col_name")}</th>
                <th>{t("settings.models.col_size")}</th>
                <th>{t("settings.models.col_role")}</th>
                <th>{t("settings.models.col_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => {
                const isChat = ollamaModelInstalled(settings.llm_model, [m.name]);
                const isEmbed = m.in_use_as === "embedding";
                const pulling = busy === `pull:${m.name}`;
                const deleting = busy === `delete:${m.name}`;
                return (
                  <tr key={m.name}>
                    <td>
                      <div className="ds-ollama-models__name">{m.name}</div>
                      {m.parameter_size && (
                        <span className="ds-ollama-models__meta">{m.parameter_size}</span>
                      )}
                    </td>
                    <td>{formatBytes(m.size)}</td>
                    <td>
                      {m.in_use_as === "llm" && (
                        <StatusBadge variant="ready" label={t("settings.models.role_chat")} />
                      )}
                      {m.in_use_as === "embedding" && (
                        <StatusBadge variant="info" label={t("settings.models.role_embedding")} />
                      )}
                      {!m.in_use_as && <span className="ds-ollama-models__muted">—</span>}
                    </td>
                    <td>
                      <div className="ds-ollama-models__actions">
                        {!isChat && !isEmbed && m.family !== "bert" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onSelectLlmModel(m.name)}
                          >
                            {t("settings.models.use_as_chat")}
                          </Button>
                        )}
                        {!m.in_use_as && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy !== null}
                            onClick={() => setDeleteTarget(m.name)}
                          >
                            <Trash2 size={14} />
                            {deleting ? t("settings.models.deleting") : t("settings.models.delete")}
                          </Button>
                        )}
                        {pulling && <span className="ds-ollama-models__muted">{t("settings.models.pulling")}</span>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        ollamaReachable && <HelpText>{t("settings.models.no_models")}</HelpText>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title={t("settings.models.delete_confirm_title")}
        message={t("settings.models.delete_confirm", { model: deleteTarget ?? "" })}
        confirmLabel={t("settings.models.delete")}
        cancelLabel={t("common.cancel")}
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && void onDelete(deleteTarget)}
      />
    </div>
  );
}
