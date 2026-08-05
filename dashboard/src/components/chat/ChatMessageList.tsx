import { useEffect, useRef } from "react";
import { useTranslation } from "../../i18n";
import type { ChatTurn } from "../../types";
import ChatUserBubble from "./ChatUserBubble";
import ChatAssistantCard from "./ChatAssistantCard";

type Props = {
  turns: ChatTurn[];
  loading: boolean;
  model?: string;
  selectedTurnIndex?: number | null;
  activeAssistantId?: string | null;
  onSelectAssistant?: (index: number) => void;
  onProcessingChange?: (processing: boolean) => void;
  density?: "product" | "engineering";
};

function isNearBottom(el: HTMLElement, threshold = 140): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

export default function ChatMessageList({
  turns,
  loading,
  model,
  selectedTurnIndex = null,
  activeAssistantId = null,
  onSelectAssistant,
  onProcessingChange,
  density = "engineering",
}: Props) {
  const { t } = useTranslation();
  const scrollRef = useRef<HTMLDivElement>(null);
  const snapRef = useRef({ turnCount: 0, streamLen: 0 });

  const isProcessing =
    loading ||
    turns.some(
      (turn) =>
        turn.role === "assistant" &&
        (turn.status === "streaming" || turn.id === activeAssistantId)
    );

  useEffect(() => {
    onProcessingChange?.(isProcessing);
  }, [isProcessing, onProcessingChange]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const turnCount = turns.length;
    const streamTurn = turns.find(
      (t) =>
        t.role === "assistant" && (t.status === "streaming" || t.id === activeAssistantId)
    );
    const streamLen = streamTurn?.text?.length ?? 0;
    const prev = snapRef.current;

    const addedTurn = turnCount > prev.turnCount;
    const addedTokens = streamLen > prev.streamLen;
    const follow = addedTurn || (addedTokens && isNearBottom(el));

    if (follow && (addedTurn || addedTokens)) {
      el.scrollTop = el.scrollHeight;
    }

    snapRef.current = { turnCount, streamLen };
  }, [turns, activeAssistantId]);

  return (
    <div className="ds-chat-main__viewport">
      <div ref={scrollRef} className="ds-chat-main__messages">
        {turns.length === 0 && !isProcessing && (
          <p className="ds-chat-main__empty">{t("chat.empty")}</p>
        )}

        {turns.map((turn, i) => {
          if (turn.role === "user") {
            return <ChatUserBubble key={turn.id || `user-${i}`} text={turn.text} />;
          }
          const sourcesState = turn.diagnostics?.sources;
          const isStreaming = turn.status === "streaming" || turn.id === activeAssistantId;
          return (
            <ChatAssistantCard
              key={turn.id || `assistant-${i}`}
              text={turn.text}
              sources={turn.sources ?? sourcesState?.items}
              sourcesStatus={sourcesState?.status ?? (turn.sources?.length ? "ready" : undefined)}
              usedContext={turn.diagnostics?.metrics.usedContext ?? turn.usedContext}
              cacheHit={turn.diagnostics?.metrics.cacheHit ?? turn.cacheHit}
              cacheType={turn.diagnostics?.metrics.cacheType ?? turn.cacheType}
              timing={turn.diagnostics?.metrics.timing as typeof turn.timing ?? turn.timing}
              metadata={turn.diagnostics?.metadata ?? turn.metadata}
              model={model}
              streaming={isStreaming}
              status={turn.status}
              selected={selectedTurnIndex === i}
              selectable={Boolean(onSelectAssistant)}
              onSelect={() => onSelectAssistant?.(i)}
              density={density}
            />
          );
        })}
      </div>

      {isProcessing && (
        <div className="ds-chat-processing-strip" role="status" aria-live="polite">
          <span className="ds-chat-processing-strip__dots" aria-hidden>
            <span />
            <span />
            <span />
          </span>
          {t("chat.processing")}
        </div>
      )}
    </div>
  );
}
