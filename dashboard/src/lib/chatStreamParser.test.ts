import { describe, expect, it, vi } from "vitest";
import {
  createChatStreamState,
  parseChatStreamChunk,
  processChatStreamLine,
  type ChatStreamCallbacks,
} from "./chatStreamParser";

describe("chatStreamParser", () => {
  it("parses token deltas and merges final response metadata", () => {
    const state = createChatStreamState();
    const tokens: string[] = [];
    const callbacks: ChatStreamCallbacks = {
      onToken: (delta) => tokens.push(delta),
    };

    const chunk = [
      "event: start",
      'data: {"request_id":"r1","session_id":"s1","streaming":true}',
      "",
      "event: retrieval",
      'data: {"sources":[{"title":"A","url":"https://a","source_type":"page","score":1}],"used_context":true}',
      "",
      "event: token",
      'data: {"delta":"Hel"}',
      "",
      "event: token",
      'data: {"delta":"lo"}',
      "",
      "event: final",
      'data: {"response":{"session_id":"s1","request_id":"r1","answer":"Hello","sources":[{"title":"A","url":"https://a","source_type":"page","score":1}],"used_context":true,"cache_hit":false,"cache_type":"none","timing":{"total_ms":1,"retrieval_ms":1,"generation_ms":0,"polish_ms":0},"trace":{"request_id":"r1","steps":[]},"metadata":{"request_id":"r1","session_id":"s1","query_intent":"faq","knowledge_version":1,"retrieval_mode":"hybrid","created_at":null}}}',
      "",
    ].join("\n");

    parseChatStreamChunk(chunk, "", state, callbacks);

    expect(tokens.join("")).toBe("Hello");
    expect(state.finalResponse).not.toBeNull();
    expect(state.finalResponse!.sources.length).toBe(1);
    expect(state.finalResponse!.trace).not.toBeNull();
    expect(state.finalResponse!.metadata?.query_intent).toBe("faq");
  });

  it("does not create duplicate final handlers", () => {
    const state = createChatStreamState();
    const onFinal = vi.fn();
    processChatStreamLine(
      'data: {"response":{"session_id":"s","request_id":"r","answer":"x","sources":[],"used_context":false,"cache_hit":false,"cache_type":"none","timing":{"total_ms":0,"retrieval_ms":0,"generation_ms":0,"polish_ms":0}}}',
      { ...state, currentEvent: "final" },
      { onFinal }
    );
    expect(onFinal).toHaveBeenCalledTimes(1);
  });
});
