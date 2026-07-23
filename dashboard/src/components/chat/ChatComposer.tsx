import { useRef, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "../../ui";
import { useTranslation } from "../../i18n";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  loading?: boolean;
};

export default function ChatComposer({ value, onChange, onSend, loading = false }: Props) {
  const { t } = useTranslation();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && value.trim()) onSend();
    }
  };

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  return (
    <div className="ds-chat-composer">
      <div className="ds-chat-composer__inner">
        <textarea
          ref={textareaRef}
          className="ds-chat-composer__input"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            autoResize();
          }}
          onKeyDown={handleKeyDown}
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.input_label")}
          disabled={loading}
          rows={1}
        />
        <Button onClick={onSend} disabled={loading || !value.trim()}>
          <Send size={16} />
          {loading ? t("common.processing") : t("common.send")}
        </Button>
      </div>
      <p className="ds-chat-composer__hint">{t("chat.composer_hint")}</p>
    </div>
  );
}
