# Migration Confidence Report (Release 0.6)

**RFC-100 Step 042** — baseline before Release 0.7 cognitive extraction.

This report documents the validated migration architecture from Steps 039–041.
It is the engineering acceptance artifact for the **Migration Confidence Gate**.

## Migration graph

```
HTTP /api/chat
    │
    ├─ KNOWLEDGE_OS_EXECUTIVE_ENABLED?
    │       YES → ExecutiveService
    │       NO  → (next)
    │
    ├─ REASONING_SERVICE_ENABLED?  (when Executive OFF, or inside Executive when ON)
    │       YES → ReasoningService
    │       NO  → RagService (legacy entry)
    │
    └─ RagService (language + caches + finalize)
            │
            ├─ REASONING + EA both ON → pipeline_provider coordinates:
            │       RPS.prepare_query → RPS.assemble_evidence → RPS.finalize_pipeline
            │
            └─ else → RetrievalPipelineService.run()
                    │
                    ├─ EVIDENCE_ASSEMBLY_ENABLED?
                    │       YES → EvidenceAssemblyService.assemble → DFP
                    │       NO  → DocumentFirstRetrievalPipeline.run
                    │
                    └─ legacy post-process adapters (broad, canonical, context, diagnostics)
```

## Feature flag matrix (validated)

| Executive | Reasoning | EA | Active path | Disabled / bypassed |
|-----------|-----------|-----|-------------|---------------------|
| OFF | OFF | OFF | Rag → RPS.run → DFP | Executive, Reasoning, EA |
| ON | OFF | OFF | Executive → Rag → RPS.run → DFP | Reasoning, EA |
| OFF | ON | OFF | Reasoning → Rag → RPS.run → DFP | Executive, EA |
| OFF | OFF | ON | Rag → RPS.run → EA → DFP | Executive, Reasoning coordinator |
| ON | ON | OFF | Executive → Reasoning → Rag → RPS.run → DFP | EA |
| ON | OFF | ON | Executive → Rag → RPS.run → EA → DFP | Reasoning coordinator |
| OFF | ON | ON | Reasoning coordinates RPS stages → EA → DFP | Executive |
| ON | ON | ON | Executive → Reasoning coordinates → EA → DFP | — |

All eight combinations: **golden smoke suite passes**; instrumented gate proves **one DFP, one LLM** per turn (caches disabled in gate harness).

## Ownership matrix (current)

| Subsystem | Owns today | Does not own |
|-----------|------------|--------------|
| **Executive** | Dispatch when flag ON; delegates | Retrieval, reasoning, language |
| **Reasoning** | Turn contract; stage order when Reasoning+EA ON | DFP, prompts, LLM, memory |
| **Evidence Assembly** | Single DFP invoke when EA ON | Intent, broad/canonical, context prose |
| **RPS (legacy coordinator)** | prepare / assemble / finalize adapters | Cognitive decisions (deferred) |
| **RagService** | Caches, prompts, LLM, polish, sources, HTTP payload assembly | Epistemic memory |
| **Language** (not extracted) | Inside Rag | — |

## Remaining legacy components

| Component | Role | Target owner (future) |
|-----------|------|------------------------|
| `RetrievalPipelineService` | Legacy coordinator | Thin further; intent → Reasoning |
| `prepare_query` | Intent + expansion adapter | Reasoning |
| `finalize_pipeline` | Broad/canonical/context adapters | Reasoning + Language split |
| `RetrievalContextBuilder` | `prompt_text` packing | Language |
| `RagService` | End-to-end answer orchestration | Language + Executive caches |
| `DocumentFirstRetrievalPipeline` | Operational retrieval tool | Evidence Assembly (wrapped) |

## Remaining god services

| Service | Status |
|---------|--------|
| **RagService** | Still primary language + cache orchestrator — **intentional** until Language extraction |
| **RPS** | Thinned to stage composition — **not** deleted; holds deferred adapters |

## Temporary adapters (documented debt)

- `pipeline_provider` on Rag — injects Reasoning-coordinated `PipelineResult`
- `legacy_result` on `ReasoningResult` — bridge to `RagResult`
- `PreparedRetrieval` — packs legacy intent/expansion for stage API
- RPS `run()` — composes three stages for non-coordinated paths

## Execution count guarantees (Step 042 gate)

Measured per request (instrumented unit harness, not wall-clock):

| Metric | Expected |
|--------|----------|
| DFP `run` | **1** |
| LLM generate / stream | **1** |
| RPS `run` OR coordinated prepare+assemble+finalize | **1 chain** |
| EA `assemble` | **0 or 1** (matches EA flag) |
| Context build | **0** with builder OFF in gate; **≤1** when ON |
| Cache read/write | **≤1** each when caches enabled |

## Parity verified

Across all flag combinations vs baseline (OFF/OFF/OFF):

- Selected hits and scores
- Context text (builder OFF in gate)
- Answer text and sources
- Response schema keys
- Golden smoke invariants
- LLM timeout error propagation
- Cache namespace unchanged
- Stream event order (`start` → … → `final`)

## Rollback independence

Each flag rolls back independently (default **OFF**):

- `KNOWLEDGE_OS_EXECUTIVE_ENABLED`
- `REASONING_SERVICE_ENABLED`
- `EVIDENCE_ASSEMBLY_ENABLED`
- `REASONING_SPEECH_ACTS_ENABLED` (Step 045 — UX only; ignored when Reasoning OFF)

No coupling requires multiple flags OFF for safe rollback. Migration confidence
gate keeps speech-acts **OFF** so answer parity vs baseline remains green.

## Future extraction points (Release 0.7+)

1. Language service extraction (prompt, LLM, polish) beyond speech-act render
2. Memory-assisted evidence (Step 047+)
3. Intent ownership move from RPS.prepare_query
4. Context builder move from RPS.finalize_pipeline

## Step 043 note (advisory sufficiency)

When `REASONING_SERVICE_ENABLED` is ON, ReasoningService computes
`evidence_sufficiency` diagnostics. This is **shadow-only** when speech-acts
are OFF — answer text and sources remain legacy-identical. EA and RPS do not
decide sufficiency.

## Step 044 note (advisory speech act)

When Reasoning is ON and speech-acts OFF, ReasoningService selects a speech act
(`answer` / `qualify` / `clarify` / `refuse`) from sufficiency. Diagnostics are
additive; answer text unchanged. Refuse means insufficient **site** evidence.

## Step 045 note (Language activation)

`REASONING_SPEECH_ACTS_ENABLED` (default false) activates Language consumption
of the typed speech-act instruction. Clarify/refuse may skip the LLM;
qualify preserves useful evidence with an explicit limitation; answer is
unchanged. Cache namespace includes `speech_act_language` when activated.
See [LANGUAGE_SPEECH_ACTS.md](LANGUAGE_SPEECH_ACTS.md) and
[0.6-step-045-speech-act-language.md](releases/0.6-step-045-speech-act-language.md).

## Validation commands

```bash
cd backend && .venv/bin/pytest tests/test_migration_confidence_gate.py -m unit -v
make release-check
```

Test harness: `backend/tests/migration/confidence_harness.py`
