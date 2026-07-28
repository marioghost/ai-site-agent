# Language layer — speech-act rendering (Release 0.6 Step 045)

**RFC-100** — Language owns final wording; Reasoning owns speech-act selection.

## Boundary

| Owner | Responsibility |
|-------|----------------|
| **Reasoning** | Select `answer` / `qualify` / `clarify` / `refuse`; reason code; typed instruction |
| **Language** | Final wording, localization, formatting, citation presentation |

Language must **not** recompute sufficiency, reinterpret retrieval scores,
choose a different speech act, inspect Epistemic Memory, write claims/tensions,
retrieve, or invent unsupported facts.

## Activation flag

`REASONING_SPEECH_ACTS_ENABLED` (default **false**).

| Reasoning | Speech acts | Behavior |
|-----------|-------------|----------|
| OFF | * | Exact legacy; speech-acts flag has **no** effect |
| ON | OFF | Step 044 advisory diagnostics only; answer unchanged |
| ON | ON | Language consumes typed instruction |

Rollback: set `REASONING_SPEECH_ACTS_ENABLED=false` (independent of Reasoning).

## Typed language instructions

| Act | Instruction |
|-----|-------------|
| answer | `ANSWER` |
| qualify | `QUALIFY_INCOMPLETE_EVIDENCE` |
| clarify | `CLARIFY_AMBIGUOUS_REQUEST` |
| refuse | `REFUSE_INSUFFICIENT_SITE_EVIDENCE` |

No free-form chain-of-thought is passed into prompts.

## Behavior

1. **answer** — legacy generation path unchanged.
2. **qualify** — LLM answer preserved; concise localized limitation appended;
   optional typed guidance injected into the existing system prompt (one LLM call).
3. **clarify** — one deterministic localized clarification question; **LLM skipped**.
4. **refuse** — site-scoped refusal wording; **LLM skipped**; no irrelevant sources.

## Sources

| Act | Sources |
|-----|---------|
| answer | Preserved |
| qualify | Preserved (completeness uncertainty ≠ remove evidence) |
| clarify | Not presented |
| refuse | Not presented as proof of refusal |

## Streaming

Deterministic clarify/refuse stream through existing `start` → … → `token` → `final`
protocol (single token, no LLM). Qualify/answer preserve token order; qualify
suffix may append as a final token delta. Streaming and non-streaming are
semantically equivalent.

## Cache

`build_retrieval_namespace(..., speech_acts_active=True)` sets
`speech_act_language=v1` only when Reasoning explicitly activates Language.
Advisory and activated answers do not share cache keys.

## Module map

| Path | Role |
|------|------|
| `backend/app/services/language/speech_act_render.py` | Templates + render plan |
| `backend/app/services/language/speech_act_decide.py` | Package retrieval → Reasoning decision |
| `RagService.answer(apply_speech_acts=…)` | Non-stream Language path |
| `RagStreamingService.iter_events(apply_speech_acts=…)` | Stream Language path |

## Diagnostics (additive)

`speech_act`, `speech_act_reason`, `speech_act_applied`, `language_instruction`,
`deterministic_response_used`, `llm_skipped`, plus understanding steps
`evidence_sufficiency_assessed` → `speech_act_selected` → `speech_act_rendered`.
