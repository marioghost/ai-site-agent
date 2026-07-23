import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { useTranslation } from "../../i18n";

type Props = {
  text: string;
  timestamp?: string;
};

export default function ChatUserBubble({ text, timestamp }: Props) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="ds-chat-user">
      <div className="ds-chat-user__bubble">{text}</div>
      <div className="ds-chat-user__row">
        {timestamp && <span className="ds-chat-user__time">{timestamp}</span>}
        <button
          type="button"
          className="ds-chat-user__copy"
          onClick={onCopy}
          aria-label={t("chat.copy")}
          title={t("chat.copy")}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
    </div>
  );
}
