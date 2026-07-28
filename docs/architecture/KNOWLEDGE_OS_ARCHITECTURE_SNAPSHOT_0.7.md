# Knowledge OS Architecture Snapshot — Release 0.7 (post–Step 050 engineering closure)

| Field | Value |
|-------|-------|
| **Status** | Official engineering baseline (Release 0.7 Engineering Ready) |
| **Scope** | Implemented code after Release 0.6 closure + Steps 046–050 |
| **Date** | 2026-07-28 |
| **App release marker** | `APP_RELEASE = "0.7"` (`build_info_service.py`); `closed_0_7: true` |
| **Alembic head (code)** | `0017_memory_canonical_shadow_enabled` |
| **Staging validated** | **false** |
| **Production ready** | **false** |
| **Rule** | This document describes **implemented** behaviour only. Roadmap items are excluded from current-state sections. |

| **049** | Offline Memory Assist evaluation | Implemented (ops package; no flag; fixtures only) |

**Staging validated:** still **false**. **Production ready:** still **false**.

---

# 1. Executive Summary

Knowledge OS today is a **flag-gated migration of a production RAG chat system** toward cognitive subsystem boundaries defined by RFC-100 / Knowledge OS Architecture v1. The product users still experience is site-grounded Q&A: normalize query → retrieve chunks from Qdrant → build context → call LLM → return answer with sources.

**What it currently is**

- A FastAPI backend (`ai-site-agent`) with Postgres, Qdrant, and Ollama.
- Chat is orchestrated by `RagService` / `RagStreamingService` on the legacy path.
- Migration seams exist so chat can optionally route through `ExecutiveService` and/or `ReasoningService`.
- Retrieval is document-first (`DocumentFirstRetrievalPipeline`), optionally wrapped by `EvidenceAssemblyService`.
- Epistemic Memory tables and region reads exist; Shadow write from Source Intelligence can persist claims when flagged.
- Steps 047–048 add **advisory** Memory assist and **diagnostic-only** canonical shadow comparison on the Reasoning coordinator path. Neither changes ranking, prompts, or answers when flags are OFF (defaults).

**What is already extracted**

| Seam | Step | Reality |
|------|------|---------|
| Executive passthrough | 001–003 | Thin shell; delegates to Reasoning or Rag |
| ReasoningService | 039–045 | Chat entry, stage ordering when coordinating, sufficiency, speech-act selection |
| EvidenceAssemblyService | 040 | Thin DFP facade; stamps `evidence_assembly_path` |
| RPS stage adapters | 041 | `prepare_query` / `assemble_evidence` / `finalize_pipeline` |
| Language speech-act render | 045 | Deterministic clarify/refuse; qualify suffix; prompt guidance |
| Epistemic Memory schema + service | 027–032 | Claims, observations, evidence links; shadow persist |
| Memory region reads | 046 | `read_region()` with deployment corpus isolation |
| Memory evidence assist | 047 | One advisory `read_region` before assemble (flagged) |
| Memory canonical shadow | 048 | Set-compare assist vs retrieval IDs (flagged, diagnostic) |
| Tension Surfacing | 035–036 | Admin understanding API; not on chat path |
| Cache namespace v2 | 023 | Optional `memory_version` in namespace |

**What still belongs to RagService**

- Semantic answer cache and retrieval cache orchestration
- Cache namespace construction (including lazy imports of Memory-assist helpers)
- Invoking `RetrievalPipelineService.run()` or a `pipeline_provider` callback
- Prompt construction (`CompactPromptBuilder`)
- LLM generation, retries, polish
- Source formatting and chat logging / traces
- Activating Language speech-act rendering when `apply_speech_acts=True`

Rag remains the **runtime request owner**. Reasoning wraps Rag; it does not replace it.

**What remains legacy**

- Intent detection, query expansion, broad-page injection, canonical source selection, and context packing inside `RetrievalPipelineService.finalize_pipeline`
- Ranking and document aggregation inside DFP
- Knowledge Profile boosts / SI routing as operational retrieval policy
- Direct chat dispatch to Rag when Executive and Reasoning flags are OFF

**Current migration philosophy (as implemented)**

1. **Default OFF** — all Knowledge OS migration flags default false.
2. **Additive seams** — new services wrap or order legacy work; they do not rewrite retrieval semantics under flags OFF.
3. **Parity first** — Step 042 golden / flag-matrix confidence for Executive × Reasoning × EA.
4. **Shadow before influence** — Memory assist and canonical shadow are advisory/diagnostic; they must not change answers until later gated steps.
5. **Independent rollback** — env and Settings flags can be turned off without schema removal.

---

# 2. Runtime Chat Pipeline

## 2.1 Dispatch (always)

```
User → POST /api/chat (or stream)
         ↓
    chat.py _dispatch_*
         ↓
    ┌─ KNOWLEDGE_OS_EXECUTIVE_ENABLED?
    │     YES → ExecutiveService
    │     NO  → REASONING_SERVICE_ENABLED?
    │              YES → ReasoningService
    │              NO  → RagService / RagStreamingService
```

**Why:** Migration entry points are additive. Chat API never hard-codes a single cognitive path.

---

## 2.2 Flags OFF (legacy production path)

All migration flags default **false**. Effective path:

```
User
  ↓
chat.py
  ↓
RagService.answer()
  ↓
normalize query
  ↓
build_retrieval_namespace()          ← no memory_version / assist keys unless Settings flags ON
  ↓
[semantic answer cache lookup]
  ↓ hit → return cached answer (skip retrieval + LLM pipeline)
  ↓ miss
[retrieval cache lookup]
  ↓ hit → reuse hits (skip DFP)
  ↓ miss
RetrievalPipelineService.run()
  ├─ prepare_query (intent, expansion, profile)
  ├─ assemble_evidence
  │     └─ DocumentFirstRetrievalPipeline.run()   ← EA flag OFF: direct DFP
  └─ finalize_pipeline
        ├─ broad inject (Settings)
        ├─ CanonicalSourceService.select_context (Settings)
        └─ ContextBuilderService
  ↓
[no speech-act Language activation]
  ↓
CompactPromptBuilder + LLM (≤1)
  ↓
optional polish
  ↓
sources + _finalize (log/trace)
  ↓
Answer
```

| Edge | Why it exists |
|------|----------------|
| chat → Rag | Legacy ownership of the chat turn |
| Rag → RPS.run | Single retrieval orchestration entry for non-coordinated path |
| RPS → DFP | Document-first retrieval implementation |
| RPS finalize → Canonical / Context | Legacy post-retrieval policy still in RPS |
| Rag → LLM | Answer generation still owned by Rag |

**Work counts (cache miss):** Retrieval/DFP = 1; Memory reads = 0; LLM ≤ 1.

---

## 2.3 Flags ON (full coordinated 0.7 path)

When Reasoning is ON and either Evidence Assembly **or** Memory assist is ON, Reasoning supplies `pipeline_provider=_coordinate_pipeline`. Typical “all ON” path:

```
User
  ↓
chat.py
  ↓
ExecutiveService                    ← if Executive ON
  ↓
ReasoningService.run()
  ↓
RagService.answer(
      pipeline_provider=_coordinate_pipeline,
      apply_speech_acts=…,
      apply_memory_assist=…)
  ↓
normalize + cache namespace
  ↓
[answer cache hit?] → return (skip pipeline, Memory, shadow, LLM)
  ↓ miss
_coordinate_pipeline (Reasoning):
  ├─ RPS.prepare_query
  ├─ MemoryAssistPolicy.attempt
  │     └─ EpistemicMemoryService.read_region (DEPLOYMENT)   ← 1 Memory read when assist effective
  ├─ RPS.assemble_evidence
  │     └─ EvidenceAssemblyService.assemble
  │           └─ DocumentFirstRetrievalPipeline.run          ← 1 DFP
  ├─ RPS.finalize_pipeline
  └─ MemoryCanonicalShadowComparator.compare_pipeline        ← 0 reads; set compare when shadow effective
  ↓
Rag attaches memory_assist / canonical_shadow diagnostics
  ↓
[REASONING_SPEECH_ACTS_ENABLED?]
  ├─ YES → language.speech_act_decide + speech_act_render
  │         ├─ skip_llm (clarify/refuse) → deterministic answer
  │         └─ else → prompt guidance into CompactPromptBuilder
  └─ NO  → continue without Language activation
  ↓
LLM (≤1) if needed
  ↓
ReasoningService._wrap
  ├─ if speech_act_applied → preserve Language diagnostics
  └─ else → assess_evidence_sufficiency + select_speech_act (advisory)
  ↓
Answer + reasoning_diagnostics
```

| Edge | Why it exists |
|------|----------------|
| Executive → Reasoning | Executive is the orchestration entry; Step 039 Reasoning is the cognitive seam |
| Reasoning → Rag | Rag still owns cache, LLM, Language activation, finalize side effects |
| Reasoning → RPS stages | Step 041: Reasoning orders prepare → assemble → finalize exactly once |
| Reasoning → MemoryAssistPolicy | Step 047: advisory Memory before assemble |
| MemoryAssist → EpistemicMemory | Only approved Memory read API for assist |
| RPS → EA → DFP | Step 040: EA owns the assemble call site; DFP does retrieval |
| Reasoning → ShadowComparator | Step 048: diagnostic compare after finalize |
| Rag → Language | Step 045: Language activates when speech-acts flag ON |
| Reasoning `_wrap` → sufficiency/speech-act | Steps 043–044 advisory when Language did not already apply |

**Work counts (cache miss, assist+shadow effective):** DFP = 1; Memory read = 1; Shadow = in-process set ops; LLM ≤ 1.

**Answer cache hit:** pipeline provider never runs → Memory assist and shadow **skipped**.

---

## 2.4 Components not on the chat path

| Component | How it is used |
|-----------|----------------|
| TensionSurfacingService | `/api/understanding` (admin) |
| EpistemicMemoryIntegrationService / shadow write | After SI generation when `memory_shadow_write_enabled` |
| SourceIntelligenceGenerationService | Indexing / admin generate-SI |
| Operational metrics | Aggregation over Memory / tensions for ops dashboards |

---

# 3. Ownership Matrix

## 3.1 ExecutiveService

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/executive/executive_service.py` |
| **Responsibilities** | Chat orchestration entry; delegate to Reasoning or Rag |
| **Public API** | `answer()`, `answer_stream()` |
| **Inputs** | message, session, request metadata, Settings, Session |
| **Outputs** | `RagResult` or stream events |
| **Dependencies** | ReasoningService, RagService, RagStreamingService, feature_flags |
| **Must never own** | Evidence, Memory, ranking, prompts, LLM, Language wording |
| **Rollout** | Env `KNOWLEDGE_OS_EXECUTIVE_ENABLED` default **false** |
| **Debt** | Thin shell only; no real multi-subsystem scheduling |

## 3.2 ReasoningService

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/reasoning/reasoning_service.py` |
| **Responsibilities** | Reasoning entry; optional RPS stage coordination; Memory assist; shadow compare; wrap sufficiency/speech-act diagnostics |
| **Public API** | `run()`, `answer()`, `answer_stream()` |
| **Inputs** | `ReasoningRequest`; Settings; Session |
| **Outputs** | `ReasoningResult` / `RagResult` with `reasoning_diagnostics` |
| **Dependencies** | RagService, RPS, MemoryAssistPolicy, MemoryCanonicalShadowComparator, evidence_sufficiency, speech_act |
| **Must never own** | ORM epistemic writes; Qdrant; LLM wording; claim proposition text in prompts |
| **Rollout** | Env `REASONING_SERVICE_ENABLED` default **false** |
| **Debt** | Holds Rag and reaches into Rag embedding/qdrant for RPS; Language activation still triggered inside Rag |

## 3.3 EvidenceAssemblyService

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/evidence_assembly/evidence_assembly_service.py` |
| **Responsibilities** | Invoke DFP exactly once; stamp `evidence_assembly_path=service` |
| **Public API** | `assemble(EvidenceAssemblyRequest) → DocumentRetrievalResult` |
| **Inputs** | Query pack (message, intent, profile, vector, expansions, language) |
| **Outputs** | `DocumentRetrievalResult` |
| **Dependencies** | DocumentFirstRetrievalPipeline only |
| **Must never own** | Reasoning, Memory, Language, sufficiency, ranking policy redesign |
| **Rollout** | Env `EVIDENCE_ASSEMBLY_ENABLED` default **false** |
| **Debt** | Pure facade; ranking remains inside DFP |

## 3.4 RetrievalPipelineService

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/retrieval_pipeline_service.py` |
| **Responsibilities** | prepare / assemble / finalize; legacy `run()` composition; diagnostics |
| **Public API** | `run()`, `prepare_query()`, `assemble_evidence()`, `finalize_pipeline()` |
| **Inputs** | message, normalized, embedding, qdrant, Settings |
| **Outputs** | `PipelineResult` (hits, context, diagnostics, optional memory_assist / canonical_shadow) |
| **Dependencies** | EA or DFP, CanonicalSourceService, ContextBuilder, SI router, intent/expansion services |
| **Must never own** | Speech acts, Memory writes, LLM |
| **Rollout** | Always on chat retrieval path |
| **Debt** | ~40% still business policy in finalize (broad inject, canonical, context) |

## 3.5 DocumentFirstRetrievalPipeline

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/retrieval_engine/pipeline.py` |
| **Responsibilities** | Hybrid retrieve → aggregate → score → rerank → selected hits |
| **Public API** | `run(...) → DocumentRetrievalResult` |
| **Inputs** | query, intent, profile, vector, expansions |
| **Outputs** | selected/rejected documents, hits, quality metrics |
| **Dependencies** | embedding, qdrant, retrieval_engine internals |
| **Must never own** | Memory, Reasoning, Language |
| **Rollout** | Production retrieval engine |
| **Debt** | Operational ranking mixed with “evidence assembly” cognitive role |

## 3.6 Language (speech acts)

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/language/speech_act_decide.py`, `speech_act_render.py` |
| **Responsibilities** | Package retrieval into sufficiency+decision; render clarify/refuse/qualify |
| **Public API** | `decision_from_retrieval()`, `plan_speech_act_render()`, `apply_qualify_suffix()`, diagnostics helpers |
| **Inputs** | hits / `SpeechActDecision`, query language |
| **Outputs** | `SpeechActRenderPlan`, diagnostics with `speech_act_applied` |
| **Dependencies** | Reasoning speech_act + evidence_sufficiency; RagResult/RagSource DTOs |
| **Must never own** | Retrieval, Memory, ranking |
| **Rollout** | Env `REASONING_SPEECH_ACTS_ENABLED` (requires Reasoning ON) default **false** |
| **Debt** | Activated from Rag, not Reasoning; depends on Rag DTOs |

## 3.7 RagService

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/rag_service.py` (+ `rag_streaming.py`) |
| **Responsibilities** | End-to-end chat turn: cache, retrieve invocation, prompt, LLM, polish, sources, logs |
| **Public API** | `answer(...)`, streaming via `RagStreamingService` |
| **Inputs** | message, session, flags (`pipeline_provider`, `apply_speech_acts`, `apply_memory_assist`) |
| **Outputs** | `RagResult` |
| **Dependencies** | RPS, caches, Ollama, CompactPromptBuilder, Language (lazy), Memory assist helpers (lazy) |
| **Must never own** (target contract) | Cognitive Memory authority, speech-act **selection** (selection is Reasoning; Rag still triggers render) |
| **Rollout** | Default chat path when Executive/Reasoning OFF |
| **Debt** | Runtime God Service; streaming duplicates non-stream logic |

## 3.8 Epistemic Memory

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/epistemic_memory/*` |
| **Responsibilities** | Persist/read claims, observations, evidence; `read_region`; corpus boundary; shadow integration |
| **Public API** | `EpistemicMemoryService`, `MemoryRegionReader.read_region`, integration persist |
| **Inputs** | proposals (SI), `MemoryRegionRequest` |
| **Outputs** | `MemoryRegionView`, claim/evidence views |
| **Dependencies** | ORM epistemic models, corpus resolver, Settings hosts |
| **Must never own** | Chat answers, ranking, Language |
| **Rollout** | Schema present; write gated by `memory_shadow_write_enabled` default **false** |
| **Debt** | Sparse real claims; assist staging NO-GO until coverage gate |

## 3.9 Tension Surfacing

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/tension_surfacing/tension_surfacing_service.py` |
| **Responsibilities** | Surface epistemic tensions for operators |
| **Public API** | Understanding API endpoints |
| **Inputs** | Memory claim/evidence views |
| **Outputs** | Tension DTOs for dashboard |
| **Dependencies** | EpistemicMemoryService |
| **Must never own** | Chat path, retrieval |
| **Rollout** | Admin-auth gated; **no** `tension_surfacing_enabled` runtime flag |
| **Debt** | Planned flag never implemented; auth gate only |

## 3.10 Memory Canonical Shadow

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `app/services/reasoning/memory_canonical_shadow_*` |
| **Responsibilities** | Compare Memory assist IDs vs context/DFP IDs; emit divergence codes |
| **Public API** | `MemoryCanonicalShadowComparator.compare_pipeline()` |
| **Inputs** | `MemoryAssistResult`, PreparedRetrieval, DocumentRetrievalResult, PipelineResult |
| **Outputs** | `MemoryCanonicalShadowResult` → diagnostics |
| **Dependencies** | Feature flags; pipeline DTOs only |
| **Must never own** | Retrieval, Memory reads, ranking, answers |
| **Rollout** | Settings `memory_canonical_shadow_enabled` default **false**; requires Reasoning+assist+cache v2 |
| **Debt** | Typed as diagnostic; eval (Step 049) not started |

## 3.11 Source Intelligence

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `source_intelligence_*` services + router |
| **Responsibilities** | Profile sources; LLM SI generation; feed retrieval routing; feed shadow claim extraction |
| **Public API** | Generation service, apply-to-source, router |
| **Inputs** | Source content / Settings |
| **Outputs** | Source profiles; claim proposals (via extraction when shadow write ON) |
| **Dependencies** | DB, optional LLM, EpistemicMemoryIntegration when flagged |
| **Must never own** | Chat Language, Executive |
| **Rollout** | Production SI used by retrieval; shadow write optional |
| **Debt** | SI ↔ Memory coupling only via shadow flag |

## 3.12 Cache

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `cache_namespace_service`, `RetrievalCacheService`, `AnswerCacheService` |
| **Responsibilities** | Namespace hash; retrieval chunk cache; semantic answer cache |
| **Public API** | `build_retrieval_namespace()`, lookup/store APIs |
| **Inputs** | Settings, knowledge/memory versions, optional assist fingerprint |
| **Outputs** | Namespace dict / hash; cached hits or answers |
| **Dependencies** | Settings, MemoryVersionService (when v2 ON) |
| **Must never own** | Reasoning decisions |
| **Rollout** | Production caches; namespace v2 Settings default **false** |
| **Debt** | Namespace build duplicated in rag + streaming; Rag imports assist helpers for keys |

## 3.13 Settings

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `models/settings.py`, `api/settings.py`, schemas |
| **Responsibilities** | Site/retrieval/LLM config; migration Settings flags |
| **Public API** | GET/PUT settings; cache clear endpoints |
| **Inputs** | Admin updates |
| **Outputs** | Settings row |
| **Dependencies** | DB |
| **Must never own** | Runtime orchestration |
| **Rollout** | Live |
| **Debt** | Chat migration flags are env-only (not mirrored in Settings DB) |

## 3.14 Operational Metrics

| Field | Current implementation |
|-------|------------------------|
| **Owner** | `operational_metrics_service.py` (+ related APIs) |
| **Responsibilities** | Aggregate ops metrics including Memory/tension signals |
| **Public API** | Metrics endpoints / build info consumers |
| **Inputs** | DB counts / Memory / tensions |
| **Outputs** | Metric DTOs |
| **Dependencies** | EpistemicMemory, TensionSurfacing (read) |
| **Must never own** | Chat answers |
| **Rollout** | Ops/dashboard |
| **Debt** | Not a cognitive subsystem; keep off chat path |

---

# 4. Feature Flag Matrix

| Flag | Default | Current Runtime | Engineering Status | Dependencies | Rollback | Current Owner | Used By |
|------|---------|-----------------|--------------------|--------------|----------|---------------|---------|
| `KNOWLEDGE_OS_EXECUTIVE_ENABLED` | false | OFF | Implemented | None | unset/false + restart | Env / `feature_flags` | `chat.py`, Executive |
| `REASONING_SERVICE_ENABLED` | false | OFF | Implemented | None | unset/false + restart | Env | chat, Executive, assist/shadow effective gates |
| `EVIDENCE_ASSEMBLY_ENABLED` | false | OFF | Implemented | None (parity validated with R/E) | unset/false + restart | Env | RPS `assemble_evidence` |
| `REASONING_SPEECH_ACTS_ENABLED` | false | OFF | Implemented | Reasoning path active | unset/false + restart | Env | Reasoning → Rag `apply_speech_acts` |
| `enable_semantic_diagnostics_v2` | false | OFF | Implemented | debug + chat debug payload | Settings false | Settings | ChatResponseBuilder |
| `cache_namespace_v2_enabled` | false | OFF | Implemented | None | Settings false | Settings | namespace hash; assist/shadow effective |
| `memory_shadow_write_enabled` | false | OFF | Implemented | SI generation path | Settings false | Settings | EpistemicMemoryIntegration |
| `memory_evidence_assist_enabled` | false | OFF | Implemented | Reasoning + cache v2 for **effective** | Settings false | Settings | MemoryAssistPolicy, cache namespace, coordinator |
| `memory_canonical_shadow_enabled` | false | OFF | Implemented | Reasoning + assist + cache v2 | Settings false | Settings | MemoryCanonicalShadowComparator |

**Effective assist:** Reasoning ON ∧ assist ON ∧ cache v2 ON.  
**Effective shadow:** assist effective ∧ shadow ON.  
**Coordination pipeline:** Reasoning ON ∧ (EA ON ∨ assist ON).

There is **no** runtime `tension_surfacing_enabled` or `claim_extraction_enabled` flag in code.

---

# 5. Data Flow

## 5.1 Chat path (website evidence → answer)

```
Source (crawled page/file)
  ↓ indexing
Chunk (+ Qdrant vectors)
  ↓ chat retrieve (DFP / RPS)
SearchHit list
  ↓ finalize (canonical / context)
BuiltContext + hits
  ↓ Rag prompt
LLM
  ↓
Answer + RagSource citations
```

**Where Reasoning touches this path today**

- May **order** prepare → assemble → finalize.
- May attach **diagnostics** (sufficiency, speech act, memory assist, shadow).
- With speech acts ON, Language may **skip LLM** or add qualify/prompt guidance.
- Memory assist **does not** inject claim text into prompts or change selected hits.

## 5.2 Memory path (SI → diagnostics)

```
Source Intelligence generation
  ↓ (memory_shadow_write_enabled)
ClaimExtractionFromSI → EpistemicMemory persist
  ↓
Epistemic tables (claims / observations / evidence_links)
  ↓ (memory_evidence_assist_enabled + prerequisites)
MemoryRegionReader.read_region(DEPLOYMENT)
  ↓
MemoryAssistResult (IDs, counts, hints — no proposition text in diagnostics)
  ↓ (memory_canonical_shadow_enabled + prerequisites)
MemoryCanonicalShadowComparator
  ↓
Diagnostics only (retrieval_debug / reasoning_diagnostics)
```

| Data | Used by chat answer? |
|------|----------------------|
| Chunks / Qdrant hits | **Yes** — grounding |
| Context prompt text | **Yes** — LLM input |
| Memory claim propositions | **No** — not in prompts |
| Memory assist source IDs | **Diagnostics only** (and cache namespace fingerprint when assist effective) |
| Canonical shadow divergence codes | **Diagnostics only** |
| Tension surfacing | **No** — admin understanding |

---

# 6. Runtime Boundaries

## 6.1 Executive

| Rule | Value |
|------|-------|
| Allowed imports | Reasoning, Rag, feature_flags, Settings |
| Forbidden imports | Epistemic ORM, DFP internals, Language render, Qdrant |
| Who may call it | `chat.py` |
| Who it may call | ReasoningService, RagService |
| Forbidden knowledge flow | Must not select evidence or write Memory |

## 6.2 Reasoning

| Rule | Value |
|------|-------|
| Allowed imports | Rag (facade), RPS DTOs/stages, MemoryAssistPolicy, ShadowComparator, speech_act, evidence_sufficiency |
| Forbidden imports | Epistemic ORM models (assist uses EpistemicMemoryService API only); Language render ownership |
| Who may call it | chat, Executive |
| Who it may call | Rag, RPS adapters, MemoryAssistPolicy, ShadowComparator |
| Forbidden knowledge flow | Claim text into prompts; Memory writes during chat |

## 6.3 Evidence Assembly

| Rule | Value |
|------|-------|
| Allowed imports | DFP, EvidenceAssemblyRequest |
| Forbidden imports | Reasoning, Memory, Language, Rag |
| Who may call it | RPS `assemble_evidence` when flag ON |
| Who it may call | DFP once |
| Forbidden knowledge flow | Sufficiency, speech acts, Memory |

## 6.4 RetrievalPipelineService

| Rule | Value |
|------|-------|
| Allowed imports | EA, DFP, canonical, context, intent/expansion, SI router |
| Forbidden imports | Epistemic Memory schema, Language speech-act package |
| Who may call it | Rag, Reasoning coordinator |
| Who it may call | EA or DFP, finalize helpers |
| Forbidden knowledge flow | Must not call LLM |

## 6.5 DocumentFirstRetrievalPipeline

| Rule | Value |
|------|-------|
| Allowed imports | retrieval_engine/*, embedding, qdrant |
| Forbidden imports | Reasoning, Memory, Language, Rag |
| Who may call it | EA, RPS (legacy assemble) |
| Who it may call | Retrievers/scorers/rerankers |
| Forbidden knowledge flow | Memory / Language |

## 6.6 Language

| Rule | Value |
|------|-------|
| Allowed imports | Reasoning speech_act + sufficiency; Rag DTOs (current leak) |
| Forbidden imports | Qdrant, RPS, Memory |
| Who may call it | Rag / RagStreaming (when speech acts applied) |
| Who it may call | Reasoning selection helpers |
| Forbidden knowledge flow | Must not retrieve or rank |

## 6.7 RagService

| Rule | Value |
|------|-------|
| Allowed imports | RPS, caches, Ollama, prompt builder; lazy Language + assist namespace helpers |
| Forbidden imports | Epistemic ORM; direct MemoryRegionReader |
| Who may call it | chat, Executive, Reasoning |
| Who it may call | RPS or pipeline_provider; Language; LLM |
| Forbidden knowledge flow | Must not persist Memory |

## 6.8 Epistemic Memory

| Rule | Value |
|------|-------|
| Allowed imports | epistemic_memory package, ORM epistemic models, corpus resolver |
| Forbidden imports | Rag, Reasoning, Language, RPS, DFP |
| Who may call it | MemoryAssistPolicy (read), Integration (write), Tension, Understanding API |
| Who it may call | MemoryRegionReader, write service |
| Forbidden knowledge flow | Must not generate chat language |

## 6.9 Memory Assist / Shadow

| Rule | Value |
|------|-------|
| Allowed imports | Assist: EpistemicMemoryService + region types; Shadow: pipeline DTOs + assist DTOs |
| Forbidden imports | Qdrant, DFP execution, prompt builders, ORM writes |
| Who may call it | Reasoning `_coordinate_pipeline` only (production) |
| Who they may call | Assist → EMS.read_region; Shadow → none (DTO compare) |
| Forbidden knowledge flow | Must not change hits, ranking, prompts, answers |

## 6.10 Tension Surfacing

| Rule | Value |
|------|-------|
| Allowed imports | EpistemicMemory views |
| Forbidden imports | Rag, RPS, chat |
| Who may call it | understanding API, operational metrics |
| Forbidden knowledge flow | Must not feed chat answers |

---

# 7. Cognitive Readiness

Scale: 1 = concept only, 3 = seam exists, 5 = production-default cognitive ownership.

| Subsystem | Concept | Implementation | Runtime | Operator | Confidence | Remaining work |
|-----------|---------|----------------|---------|----------|------------|----------------|
| Executive | 4 | 3 | 2 | 3 | Medium | Still passthrough |
| Reasoning | 4 | 4 | 2 | 3 | Medium | Not default; wraps Rag |
| Evidence Assembly | 4 | 3 | 2 | 3 | Medium-High | Thin facade |
| Retrieval Pipeline | 3 | 4 | 5 | 4 | High | Legacy policy in finalize |
| DFP | 3 | 5 | 5 | 4 | High | Operational, not cognitive |
| Language (speech acts) | 4 | 4 | 2 | 2 | Medium | Flag OFF; Rag-triggered |
| RagService | 2 | 5 | 5 | 4 | High | Shrink over releases |
| Epistemic Memory | 4 | 4 | 2 | 2 | Medium | Sparse corpus; flags OFF |
| Memory Assist | 4 | 4 | 1 | 1 | Medium | Staging NO-GO |
| Canonical Shadow | 4 | 4 | 1 | 1 | Medium | Diagnostics only; no eval yet |
| Tension Surfacing | 4 | 4 | 3 | 3 | Medium | Admin only |
| Source Intelligence | 3 | 5 | 5 | 4 | High | Mature operational |
| Cache | 3 | 5 | 5 | 4 | High | v2 optional |
| Settings / Flags | 4 | 5 | 5 | 4 | High | Doc/UI lag cleaned; env vs Settings split remains |

**Honest overall:** Cognitive **seams** are real. Cognitive **default runtime** is still legacy Rag + DFP. Memory does not yet own chat evidence.

---

# 8. Technical Debt

## Critical

| Debt | Target |
|------|--------|
| Sparse Memory coverage — assist must not be staging-default ON until gate | Before assist staging enable |
| Documentation/step numbering drift risk (mitigated by this snapshot + cleanup) | Maintain via snapshot |

## Medium

| Debt | Target |
|------|--------|
| RagService remains request God Service | 0.8–1.0 |
| Reasoning ↔ Rag logical cycle (lazy imports) | 0.8 |
| Language activated inside Rag | 0.8 |
| `evidence_sufficiency` / Language depend on `RagResult` | 0.8 |
| RPS finalize still owns broad inject + canonical + context | 0.8 (esp. Step 055 canonical) |
| Rag / streaming duplicate cache+pipeline blocks | 0.8 |
| Cache namespace helpers imported from Reasoning into Rag | 0.8 |
| Env-only chat flags vs Settings-only Memory flags | 1.0 registry cleanup |
| Pre-existing unit boundary test vs approved Step 047 Memory imports in assist policy | Cleanup / test update |

## Low

| Debt | Target |
|------|--------|
| Weak historical `object` typing (largely cleaned) | Maintain |
| Fingerprint call-path multiplicity (algorithm unified) | 0.8 polish |
| Path marker naming proliferation | Docs |
| Dashboard / build metadata lag (improved in cleanup) | Maintain |

---

# 9. Release Status

| Release | Engineering | Staging | Production | Flags | Notes |
|---------|-------------|---------|------------|-------|-------|
| **0.4** Memory schema + shadow write | Accepted | Per release reports | Shadow write OFF | `memory_shadow_write_enabled` | Additive tables |
| **0.5** Tension surfacing | Accepted | Admin gated | Auth gate | No dedicated flag | Understanding API |
| **0.6** Reasoning / EA / speech acts | **Accepted** (`closed_0_6: true`) | Not required for closure | Flags OFF | Env flags OFF | Steps 039–045 |
| **0.7** Memory assist + shadow + offline eval | **Accepted** (`closed_0_7: true`; Engineering Ready) | **staging_validated: false** | **production_ready: false** | Assist + shadow Settings OFF | Steps 046–050; Release 0.8 not started |

**Outstanding blockers for staging activation (not for engineering closure):**

1. Memory coverage gate for assist staging.
2. Real staging diagnostics harvest + Step 049 recommendation on real data.
3. Explicit approval before any controlled assist/shadow experiment.
4. All migration flags remain default OFF in runtime until that approval.

---

# 10. Architectural Invariants

These MUST NEVER be broken while this snapshot is the baseline.

### Chat & execution

1. **Flags OFF equals legacy behaviour** for user-visible answers (golden parity).
2. **Retrieval / DFP executes at most once** per uncached chat turn on the coordinated path.
3. **LLM executes at most once** per turn (zero for deterministic clarify/refuse).
4. **Answer cache hit skips** retrieval pipeline, Memory assist, and shadow.
5. **Executive never owns evidence** selection or Memory state.
6. **Reasoning never owns Language wording** (selection vs render split).
7. **Language never performs retrieval** or Qdrant access.
8. **Language never mutates Memory**.

### Evidence Assembly & Retrieval

9. **Evidence Assembly never performs Reasoning** (no sufficiency/speech acts).
10. **Evidence Assembly never reads/writes Memory**.
11. **Evidence Assembly invokes DFP exactly once** per `assemble()` call.
12. **RPS must not call LLM**.
13. **DFP must not import Reasoning, Memory, or Language**.

### Memory & Shadow

14. **Memory never generates language** for chat.
15. **Memory never mutates during a chat turn** (assist is read-only).
16. **Memory assist never injects claim proposition text into prompts**.
17. **Memory assist never changes ranking, canonical selection, or hit lists**.
18. **Canonical Shadow never affects ranking**.
19. **Canonical Shadow never changes answers**.
20. **Canonical Shadow never performs retrieval, DFP, or `read_region()`**.
21. **Shadow diagnostics expose IDs/codes only** — no claim/chunk/prompt/answer text.
22. **Support-source diagnostics reflect support-role evidence**, not all assist sources conflated.
23. **Epistemic Memory services must not import Rag / RPS / DFP / Language**.

### Reasoning boundaries

24. **Reasoning assist path uses EpistemicMemoryService API**, not epistemic ORM models directly.
25. **Reasoning must not bump MemoryVersion or KnowledgeVersion** on chat.
26. **Speech-act selection is deterministic and advisory** when Language flag is OFF.

### Cache & flags

27. **Cache namespace v2 OFF** ⇒ `memory_version` ignored for keys.
28. **Assist ineffective without** Reasoning + assist flag + cache v2.
29. **Shadow ineffective without** assist effective + shadow flag.
30. **Independent rollback**: disabling any single migration flag must not require schema downgrade for safe chat rollback.
31. **Shadow write OFF** ⇒ zero epistemic writes from SI integration path.

### Tension & ops

32. **Tension Surfacing is not on the chat path**.
33. **Operational metrics must not alter retrieval or answers**.

### Corpus / versions

34. **Chat must not rewrite Source/Chunk corpora**.
35. **knowledge_version and memory_version are distinct**; Memory bumps do not change knowledge_version.

---

# 11. Current Runtime Diagram

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        Knowledge OS — Runtime Snapshot 0.7               │
│                     (flags default OFF → bold path is legacy Rag)        │
└──────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────┐
                         │    User     │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │  chat API   │
                         └──────┬──────┘
            ┌───────────────────┼───────────────────┐
            │ Executive ON      │ Reasoning ON      │ both OFF
            ▼                   ▼                   ▼
     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
     │  Executive  │────▶│  Reasoning  │────▶│ RagService  │◀── default
     └─────────────┘     └──────┬──────┘     └──────┬──────┘
                                │                   │
                    coordinate? │                   │ run()
                    (EA|assist) │                   │
                                ▼                   ▼
                     ┌──────────────────┐   ┌──────────────────┐
                     │ Memory Assist *  │   │ RetrievalPipeline│
                     │ read_region ×1   │   │ prepare/assemble │
                     └────────┬─────────┘   │ /finalize        │
                              │             └────────┬─────────┘
                              ▼                      │
                     ┌──────────────────┐            │
                     │ Evidence Assy *  │────────────┤
                     │     or DFP       │            │
                     └────────┬─────────┘            │
                              ▼                      │
                     ┌──────────────────┐            │
                     │      DFP ×1      │◀───────────┘
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ finalize (RPS)   │  broad / canonical / context
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Canonical Shadow*│  diagnostics only
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Language speech *│  if speech-acts ON
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │   LLM ≤1 / skip  │
                     └────────┬─────────┘
                              ▼
                         ┌─────────┐
                         │ Answer  │
                         └─────────┘

  * Optional, flag-gated. Default OFF.

Off-chat (implemented, separate):
  SI ──shadow write*──▶ Epistemic Memory ──▶ Tension Surfacing (admin)
```

---

# 12. Engineering Verdict

| Dimension | Verdict |
|-----------|---------|
| **Architecture health** | **Good seams, tangled runtime.** Boundaries for EA, Memory, and Shadow are clean. Reasoning/Rag/Language form a workable but cyclic orchestration cluster. |
| **Migration progress** | Release **0.6 closed**. Release **0.7 closed** (Steps **046–050** Engineering Ready) with flags OFF. Not staging-validated. |
| **Remaining releases** | Release **0.8 not started**. 0.8+ for Rag shrink / canonical Memory influence. 1.0 for default-ON migration. |
| **Readiness for staging activation** | **Blocked** until real diagnostics harvest + Step 049 recommendation. Synthetic fixtures are not live recommendations. |
| **Known risks** | Enabling assist/shadow before coverage/eval; treating diagnostics as product behaviour; Rag/streaming drift; sparse Memory misread as “no knowledge.” |
| **Recommendation** | Treat this document as the **current-state baseline** at 0.7 engineering closure. Do not enable 0.7 Memory flags in staging until coverage gate + real eval report say so. Do not start Release 0.8 under this closure task. |

---

**End of snapshot. Release 0.7 engineering closed (Step 050). Release 0.8 not started.**
