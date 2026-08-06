import { describe, expect, it } from "vitest";
import { createAssistantPlaceholder, mergeAssistantFromResponse } from "./messageRepository";
import { reduceStreamEvent } from "./streamingReducer";
import { messageToTurn } from "../lib/chatTurnDiagnostics";
import type { ChatMessage } from "../types";

describe("streamingReducer", () => {
  it("updates the same assistant turn through stream lifecycle without duplicating text paths", () => {
    let turn = createAssistantPlaceholder("sess", "");
    turn = reduceStreamEvent(turn, {
      type: "start",
      requestId: "req-1",
      sessionId: "sess",
    });
    expect(turn.status).toBe("streaming");
    expect(turn.diagnostics?.pipeline.some((s) => s.name === "receive_request" && s.status === "completed")).toBe(
      true
    );

    turn = reduceStreamEvent(turn, {
      type: "retrieval",
      sources: [{ title: "A", url: "https://a", source_type: "page", score: 0.9 }],
      usedContext: true,
      cacheHit: false,
      cacheType: "none",
    });
    expect(turn.diagnostics?.sources.status).toBe("ready");
    expect(turn.sources).toHaveLength(1);

    turn = reduceStreamEvent(turn, { type: "token", delta: "Hel" });
    turn = reduceStreamEvent(turn, { type: "token", delta: "lo" });
    expect(turn.text).toBe("Hello");

    turn = reduceStreamEvent(turn, {
      type: "final",
      response: {
        session_id: "sess",
        request_id: "req-1",
        answer: "Hello",
        sources: turn.sources ?? [],
        used_context: true,
        cache_hit: false,
        cache_type: "none",
        timing: { total_ms: 10, retrieval_ms: 3, generation_ms: 7, polish_ms: 0 },
        trace: null,
        metadata: null,
      },
    });
    expect(turn.status).toBe("completed");
    expect(turn.response?.answer).toBe("Hello");
    expect(turn.diagnostics?.status).toBe("completed");
    expect(
      turn.diagnostics?.pipeline.every((s) => s.status === "completed" || s.status === "skipped")
    ).toBe(true);
    expect(turn.diagnostics?.pipeline.some((s) => s.status === "pending")).toBe(false);
  });

  it("marks truncated when prompt_diagnostics.output_truncated is true", () => {
    let turn = createAssistantPlaceholder("sess", "");
    turn = reduceStreamEvent(turn, {
      type: "start",
      requestId: "req-2",
      sessionId: "sess",
    });
    turn = reduceStreamEvent(turn, { type: "token", delta: "Partial" });
    turn = reduceStreamEvent(turn, {
      type: "final",
      response: {
        session_id: "sess",
        request_id: "req-2",
        answer: "Partial mid-wor",
        sources: [],
        used_context: true,
        cache_hit: false,
        cache_type: "none",
        timing: { total_ms: 10, retrieval_ms: 3, generation_ms: 7, polish_ms: 0 },
        trace: null,
        metadata: null,
        prompt_diagnostics: {
          output_truncated: true,
          generation_stop_reason: "length",
          done_reason: "length",
          num_predict: 180,
          eval_count: 180,
        },
      },
    });
    expect(turn.status).toBe("truncated");
    expect(turn.diagnostics?.status).toBe("truncated");
  });

  it("preserves truncated after post-stream mergeAssistantFromResponse", () => {
    let turn = createAssistantPlaceholder("sess", "req-3");
    turn = reduceStreamEvent(turn, {
      type: "final",
      response: {
        session_id: "sess",
        request_id: "req-3",
        answer: "Cut off…",
        sources: [],
        used_context: true,
        cache_hit: false,
        cache_type: "none",
        timing: { total_ms: 10, retrieval_ms: 1, generation_ms: 9, polish_ms: 0 },
        trace: null,
        metadata: null,
        prompt_diagnostics: { output_truncated: true, generation_stop_reason: "length" },
      },
    });
    turn = mergeAssistantFromResponse(turn, {
      session_id: "sess",
      request_id: "req-3",
      answer: "Cut off…",
      sources: [],
      used_context: true,
      cache_hit: false,
      cache_type: "none",
      timing: { total_ms: 10, retrieval_ms: 1, generation_ms: 9, polish_ms: 0 },
      trace: null,
      metadata: null,
      prompt_diagnostics: { output_truncated: true, generation_stop_reason: "length" },
    });
    expect(turn.status).toBe("truncated");
    expect(turn.diagnostics?.status).toBe("truncated");
  });
});

describe("messageToTurn truncation persistence", () => {
  it("hydrates truncated from persisted prompt_diagnostics", () => {
    const message = {
      id: 42,
      session_id: "sess",
      role: "assistant",
      content: "Incomplete…",
      sources: [],
      used_context: true,
      cache_hit: false,
      cache_type: "none",
      request_id: "req-h",
      timing: { total_ms: 1, retrieval_ms: 0, generation_ms: 1, polish_ms: 0 },
      diagnostics: {
        prompt_diagnostics: {
          output_truncated: true,
          generation_stop_reason: "length",
          done_reason: "length",
        },
      },
    } as unknown as ChatMessage;
    const turn = messageToTurn(message);
    expect(turn.status).toBe("truncated");
    expect(turn.diagnostics?.status).toBe("truncated");
  });
});
