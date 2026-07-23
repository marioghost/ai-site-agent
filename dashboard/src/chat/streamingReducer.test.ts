import { describe, expect, it } from "vitest";
import { createAssistantPlaceholder } from "./messageRepository";
import { reduceStreamEvent } from "./streamingReducer";

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
  });
});
