# Architecture Contract 1.0

**Status:** Binding constitution of the AI Platform  
**Effective:** Phase 0 Knowledge Understanding foundation complete  
**Authority:** Supplements — does not replace — `KNOWLEDGE_OS_ARCHITECTURE_v1.md`, `COGNITIVE_ARCHITECTURE.md`, `RFC-0001-KNOWLEDGE-OS-CORE.md`, `ENGINEERING_MANIFEST.md`, `DEVELOPMENT_CHARTER.md`  
**Change control:** Boundary, ownership, event, or public API changes require an **ADR**. Bug fixes and in-subsystem execution do not.  
**Audience:** Every engineer, reviewer, and agent working on this codebase  

> This document freezes what the system *is*. Future PRs comply with it. Ambiguity is resolved in favor of existing owners and the valid execution flow below.

---

## 0. How to use this contract

1. Before implementing: identify the owning subsystem (§2–§3).
2. Verify the change belongs there. If not → stop → ADR or relocate work.
3. Verify imports against §5.
4. Verify invariants §7–§9.
5. Complete the PR checklist §10 before merge.

Violating this contract is an architectural defect, not a style preference.

---

## 1. Core architectural philosophy

### 1.1 What the platform is

This product is a **Knowledge OS**: a system that understands website knowledge and answers from that understanding.

It is **not**:

- a document search appliance
- a chunk/embedding product
- a knowledge-graph product
- an admin-tuned ranking console
- an industry template engine

Retrieval, graphs, embeddings, indexes, and prompts are **tools and representations**. Understanding and epistemic truth are the center.

### 1.2 Why the system is organized this way

| Problem | Architectural response |
|---------|------------------------|
| Pages ≠ knowledge | Source Intelligence interprets pages; Understanding aggregates site-wide meaning; Epistemic Memory holds claims |
| Search ≠ answering | Query planning → evidence assembly → evidence planning → generation; ranking is a tool inside assembly |
| Hardcoded domains don’t scale | Zero Hardcode Policy; inference over config; tenant-agnostic SI → Understanding |
| God pipelines can’t evolve | Named subsystems with single ownership; Executive coordinates |
| Graphs become fashion | Understanding exposes capabilities, not nodes/edges; representation is swappable |
| Diagnostics that mutate truth | Diagnostics are read-only projections |
| Multi-tenant SaaS | No tenant-specific code paths; knowledge emerges per corpus |

### 1.3 Governing mental model

```
Website
  → Source Intelligence (per-page interpretation)
  → Knowledge Understanding (site-wide semantic model)
  → Epistemic Memory (claims / beliefs — sole epistemic truth store)
  → Reasoning (information need → belief / speech act)
  → Evidence Assembly (retrieval as tool when memory alone is insufficient)
  → Language / Generation (presentation)
```

Operational chat today still runs a mature **document-first RAG path** inside Evidence Assembly. That path is **frozen as the successful retrieval tool**, not as the product identity.

### 1.4 What “complete foundation” means

The foundation is complete when:

1. Cognitive / Knowledge OS subsystem map is frozen (`KNOWLEDGE_OS_ARCHITECTURE_v1.md`).
2. Operational RAG stage ownership is frozen (`rag-v2.1` / this contract §2).
3. Knowledge Understanding Layer Phase 0 exists: capability interface, SI-driven rebuild, concept-index store, no ranking wire yet.
4. Zero Hardcode and no-admin-tuning rules are enforced as architecture, not preference.

Phase 1+ (Understanding → shadow ranking assist, Memory-driven selection, graph adapter if proven) **extends** this contract at approved insertion points (§6). It does not reopen §2–§5.

---

## 2. Subsystem boundaries

Two layers exist. They must not be collapsed:

| Layer | Document | Role |
|-------|----------|------|
| **Cognitive (Knowledge OS)** | `KNOWLEDGE_OS_ARCHITECTURE_v1.md` Part 2 | Executive, Reasoning, Epistemic Memory, Evidence Assembly, Language, Diagnostics, … |
| **Operational (RAG + Understanding)** | This contract §2 | Planner, Retrieval, Evidence, Generation, Understanding, Source Intelligence, Diagnostics, Knowledge Store |

Operational subsystems are **implementation owners** of the live chat/index path. Cognitive subsystems are **authority** for long-term truth and migration. When they conflict, **cognitive ownership wins** and operational code must migrate toward it (ADR if boundaries move).

---

### 2.1 Planner

**Implementation:** `QueryPlanner` — `backend/app/services/rag_planning/query_planner.py`  
**Also:** Query understanding / intent analysis feeding the plan (`QueryUnderstandingService`, retrieval intent services)

| | Rule |
|--|------|
| **Responsibilities** | Infer information need from the user query; produce a retrieval/evidence plan (intent, focus, expected evidence, scope, language signals); never fetch documents |
| **Forbidden** | Vector/lexical search; document scoring; prompt text; LLM generation; mutating SI, Understanding, or Memory; admin-tunable weight tables |
| **Allowed dependencies** | Settings (feature flags, non-intelligence config); Knowledge Profile *read* only where still legacy-gated; QueryUnderstanding types |
| **Forbidden dependencies** | `DocumentFirstRetrievalPipeline`; `EvidencePlanner` outputs as inputs to re-plan mid-flight; Understanding Store writes; Epistemic Memory writes |

**Invariant:** Planner plans. It does not retrieve.

---

### 2.2 Retrieval

**Implementation:** `DocumentFirstRetrievalPipeline` and leaf modules under `backend/app/services/retrieval_engine/`  
**Coordinator:** `RetrievalPipelineService` (`prepare_query` / `assemble_evidence` / `finalize_pipeline`)  
**Facade (when enabled):** `EvidenceAssemblyService`

| | Rule |
|--|------|
| **Responsibilities** | Given a plan, discover and rank **candidate evidence documents**; hybrid retrieve; aggregate; score; rerank; attach selection explanations; consume SI profiles as *signals*, not as ontology |
| **Forbidden** | Owning product identity (“we are a search engine”); prompt assembly; streaming tokens; claim truth; site-wide concept model ownership; admin-exposed boost maps / industry rules |
| **Allowed dependencies** | Planner outputs; Source SI fields (read); Qdrant/embeddings infrastructure; Settings operational knobs that are not “intelligence”; optional Understanding *read* only via approved Phase 1+ assist merge (not yet wired) |
| **Forbidden dependencies** | PromptBuilder; LlmGenerationService; Epistemic Memory writes; Diagnostics writes; Knowledge Understanding rebuild |

**Frozen successful path (do not redesign):**

```
Query → QueryPlanner → DocumentFirstRetrievalPipeline → EvidencePlanner
      → RetrievalContextBuilder → CompactPromptBuilder → LlmGenerationService
```

**Invariant:** Retrieval retrieves evidence candidates. It does not understand the site and does not speak to the user.

---

### 2.3 Evidence

**Implementation:** `EvidencePlanner` — `backend/app/services/evidence_planning/`; context serialization `RetrievalContextBuilder` (+ `ContextBuilderService` flatten helpers); sufficiency/coverage validators on the RAG contract

| | Rule |
|--|------|
| **Responsibilities** | Select/order/budget evidence for the prompt from retrieval candidates; enforce coverage/sufficiency policy; serialize context for generation; explain selection at evidence-plan level |
| **Forbidden** | Re-running vector search as primary mission; inventing new documents; generating answers; mutating Memory/Understanding; hardcoding document-type boost tables |
| **Allowed dependencies** | Retrieval candidate set + scores/explanations; Planner need signals; Settings for budgets/limits |
| **Forbidden dependencies** | CompactPromptBuilder internals; Ollama generation; SI batch writers |

**Invariant:** Evidence prepares what may be said. It does not say it.

---

### 2.4 Generation

**Implementation:** `CompactPromptBuilder` — `retrieval_engine/prompt_builder.py`; `LlmGenerationService`; streaming `RagStreamingService`; Language speech-act render when flags allow

| | Rule |
|--|------|
| **Responsibilities** | Render prompts from planned context; call the LLM; stream tokens; apply speech-act presentation decisions supplied by Reasoning |
| **Forbidden** | Choosing which sources are true; re-ranking the corpus; writing Memory/Understanding; inventing retrieval; admin prompt templates as domain ontology |
| **Allowed dependencies** | Evidence/context bundle; Reasoning speech-act decisions (read); LLM/Ollama infrastructure; Settings timeouts/models |
| **Forbidden dependencies** | DocumentFirstRetrievalPipeline; Understanding rebuild; Epistemic write path |

**Invariant:** PromptBuilder renders. Generation generates. Neither plans nor retrieves.

---

### 2.5 Understanding (Knowledge Understanding Layer)

**Implementation:** `backend/app/services/knowledge_understanding/`  
**Interface:** `KnowledgeUnderstandingLayer` Protocol  
**MVP adapter:** `ConceptIndexUnderstandingLayer`  
**Rebuild:** `UnderstandingRebuildService` (after SI finalize)

| | Rule |
|--|------|
| **Responsibilities** | Build and serve **site-wide semantic understanding** from SI; resolve query → knowledge need; find evidence candidates by understanding; expose coverage gaps and human `why` matches; persist versioned understanding snapshots |
| **Forbidden** | Graph APIs to callers; node/edge admin editors; industry synonym tables; regex synonym maps; tenant-specific merge rules; owning claim truth (that is Epistemic Memory); replacing DFP; mutating Source SI |
| **Allowed dependencies** | Source `intelligence_json` (read); embeddings; `knowledge_version`; Settings flag `enable_knowledge_understanding` for query-time enablement |
| **Forbidden dependencies** | QueryPlanner / DFP / EvidencePlanner / PromptBuilder / Generation (Understanding must not import the frozen RAG owners); Epistemic Memory write APIs |

**Phase 0 law:** Rebuild after SI is mandatory. Ranking integration is **not** enabled until Phase 1 shadow (flagged). Until then, calling Understanding from Retrieval is an architectural violation unless behind the approved shadow insertion point (§6.1).

**Invariant:** Understanding understands. Representation (concept index today, optional graph later) is internal.

---

### 2.6 Source Intelligence

**Implementation:** `SourceIntelligenceService`, `SourceIntelligenceGenerationService`, LLM/rules helpers, router  
**Storage (transitional):** columns + `intelligence_json` on `Source`

| | Rule |
|--|------|
| **Responsibilities** | Per-source structural + semantic interpretation at index/SI-batch time; write SI fields onto Source; trigger downstream shadow Memory integrate and Understanding rebuild on finalize |
| **Forbidden** | Site-wide concept index ownership; chat answer generation; admin ontology editing; hardcoding banks/products/industries; becoming the long-term epistemic truth store |
| **Allowed dependencies** | Source content; embedding/LLM infrastructure; Settings SI flags; ClaimExtractionFromSI proposals (handoff only) |
| **Forbidden dependencies** | Chat Executive path; PromptBuilder; Understanding Store internals (call rebuild service only at finalize) |

**Invariant:** SI interprets pages. It does not own site-wide understanding or claim truth.

---

### 2.7 Diagnostics

**Implementation:** `RetrievalDiagnostics` / `DiagnosticsBuilder` / `ExplanationBuilder`; `TraceBuilder`; chat `DiagnosticsCollector` / `ChatResponseBuilder`; KUL `diagnostics.py`; Reasoning diagnostics; Memory shadow comparators (diagnostic only)

| | Rule |
|--|------|
| **Responsibilities** | Project human-readable explanations of decisions (`why_selected` / `why_rejected` / understanding traces / traces); aggregate observability |
| **Forbidden** | Mutating Epistemic Memory; feeding scores back into ranking automatically; owning retrieval mission; storing “truth” |
| **Allowed dependencies** | Read-only views of Planner/Retrieval/Evidence/Understanding/Reasoning outputs |
| **Forbidden dependencies** | Writers to Memory, Understanding Store (except reading), Source SI |

**Invariant:** Diagnostics observes. It never decides and never writes knowledge.

---

### 2.8 Knowledge Store

“Knowledge Store” is a **persistence domain**, not one class. Sub-owners:

| Store | Owner | Contents |
|-------|--------|----------|
| **Understanding Store** | Knowledge Understanding | `understanding_snapshots` / concepts / evidence links (site-wide semantic model) |
| **Epistemic Memory** | Epistemic Memory subsystem | Claims, evidence links, observations (sole epistemic truth) |
| **Retrieval index** | Evidence Assembly / infrastructure | Vectors, chunks, lexical indexes (evidence containers, not truth) |
| **Source SI fields** | Source Intelligence (transitional) | Per-page profiles until fully claimed into Memory |

| | Rule |
|--|------|
| **Responsibilities** | Persist and version knowledge artifacts under the correct owner; support rebuild/invalidation via `knowledge_version` / `memory_version` |
| **Forbidden** | One mega-table owning all meaning; Retrieval writing claims; Understanding writing claims; Dashboard editing ontologies |
| **Allowed dependencies** | Owning subsystem services only |
| **Forbidden dependencies** | Cross-store writes (Understanding must not write epistemic tables; Memory must not write understanding snapshots) |

**Invariant:** Every persisted knowledge artifact has exactly one owning subsystem.

---

### 2.9 Coordination subsystems (binding, even if not in the short list)

These are already frozen in Knowledge OS v1 and remain binding:

| Subsystem | Owns | Must never own |
|-----------|------|----------------|
| **Executive** | Chat entry, orchestration, refusal authority | Claims, prompts, retrieval ranking |
| **Reasoning** | Request-scoped inference, speech acts, sufficiency | Memory mutations, crawl, NL fluency |
| **Language** | Presentation of authorized speech acts | Epistemic decisions |
| **Evidence Assembly** | Thin assembly facade over retrieval tools | Belief revision; product ranking mission |
| **Epistemic Memory** | All knowledge state | Crawl queues, sessions, raw files as cognition |
| **Memory Integration** | Claim revision semantics | User-facing language |
| **Epistemic Maintenance** | What to learn next | Fetch execution; answers |

---

## 3. Ownership rules

Every responsibility has **exactly one owner**.

| Responsibility | Sole owner |
|----------------|------------|
| HTTP chat entry / concurrency / refusal gate | Executive |
| Information-need plan from query | Planner (`QueryPlanner` + query understanding) |
| Candidate document discovery & scoring | Retrieval (`DocumentFirstRetrievalPipeline`) |
| Pipeline coordination prepare/assemble/finalize | `RetrievalPipelineService` (operational); Evidence Assembly facade when enabled |
| Evidence budget / selection for prompt | Evidence (`EvidencePlanner`) |
| Context serialization | `RetrievalContextBuilder` |
| Prompt rendering | `CompactPromptBuilder` |
| Token generation / streaming | `LlmGenerationService` / `RagStreamingService` |
| Speech-act presentation | Language (under Reasoning authorization) |
| Per-page semantic/structural profile | Source Intelligence |
| Site-wide concept/evidence understanding model | Understanding (KUL) |
| Understanding rebuild after SI | `UnderstandingRebuildService` |
| Claim proposals from SI | Claim Extraction |
| Claim persistence / revision | Epistemic Memory / Memory Integration |
| Advisory memory region read before assemble | `MemoryAssistPolicy` (Reasoning) — advisory only |
| `knowledge_version` bump on SI content change | `KnowledgeVersionService` (triggered from SI finalize) |
| `memory_version` bump on shadow claim create | Memory Integration only |
| Human explainability projection | Diagnostics |
| Feature flag definitions / effective resolution | `feature_flags` registry |
| Deploy / release identity | Release engineering (`manage_deploy.sh` / release workflow) |

**Conflict rule:** If two modules appear to own the same responsibility, the owner in this table wins; the other must delete or relocate the logic.

---

## 4. Data flow — the only valid execution flows

Anything outside these flows is an **architectural violation** unless an ADR amends this section.

### 4.1 User question (production chat)

```
User
  → API chat
  → ExecutiveService
  → ReasoningService                    # when REASONING_SERVICE_ENABLED
       → prepare_query (Planner)
       → MemoryAssistPolicy.attempt     # advisory read; fail-open; no writes
       → assemble_evidence
            → EvidenceAssemblyService   # when EVIDENCE_ASSEMBLY_ENABLED
                 → DocumentFirstRetrievalPipeline
       → finalize_pipeline
       → EvidencePlanner
       → RetrievalContextBuilder
       → CompactPromptBuilder
       → LlmGenerationService / stream (+ Language speech acts when enabled)
  → response (+ Diagnostics projection)
```

**Forbidden shortcuts:**

- Chat API → RagService bypassing Executive when Executive flag is ON  
- Generation calling Retrieval  
- Retrieval writing Memory or Understanding  
- Diagnostics writing Memory  
- Understanding silently changing DFP scores outside Phase 1+ flagged assist  

### 4.2 Index / Source Intelligence batch

```
Source content
  → Source Intelligence build/apply → Source row (SI fields)
  → EpistemicMemoryIntegrationService.shadow_write_after_si   # if flag ON
  → finalize_generation
       → KnowledgeVersionService.bump
       → optional cache invalidation
       → UnderstandingRebuildService.rebuild_after_si         # soft-fail
```

### 4.3 Understanding query-time (Phase 0 capability; Phase 1 wire)

```
QueryUnderstanding / QueryNeedInput
  → KnowledgeUnderstandingLayer.resolve_query
  → find_evidence / explain_match / understanding_trace
```

**Phase 0:** available to admin/diagnostics APIs; **not** inserted into §4.1 ranking.  
**Phase 1+:** may merge understanding candidates into assemble_evidence **only** at the approved insertion point (§6.1), behind `enable_knowledge_understanding`, shadow-first.

### 4.4 Maintenance / active acquisition

Follows Knowledge OS v1 lifecycles (Executive → Maintenance → Indexing Gateway → Observation → Claim → Memory). Must not invent a parallel “retrain ranking” loop.

---

## 5. Dependency rules

### 5.1 Allowed direction (DAG)

```
API → Executive → Reasoning → Rag / Language / LLM
                 ↘
                  RetrievalPipelineService → EvidenceAssembly → Retrieval (DFP)
                                           → Evidence → Prompt → Generation

Indexing / SI → Source
             → Memory Integration → Epistemic Memory
             → Understanding Rebuild → Understanding Store

Diagnostics ← (reads) all of the above
Analytics   ← (reads) aggregates
```

### 5.2 Forbidden imports / call directions

| From | Must not import / call |
|------|-------------------------|
| Understanding package | `retrieval_engine.pipeline`, `evidence_planning`, `prompt_builder`, `rag_service`, Executive |
| Retrieval / DFP | Understanding Store writers; Epistemic Memory writers; PromptBuilder; LlmGenerationService |
| EvidencePlanner | DFP.run; Understanding rebuild; Memory writers |
| PromptBuilder / Generation | DFP; Understanding rebuild; Memory writers |
| Diagnostics | Any knowledge writers |
| Epistemic Memory region reader | RagService, RPS, EA, Reasoning (keep read boundary) |
| Dashboard product UI | Retrieval tuning controls; ontology editors; Understanding graph explorers |

### 5.3 Soft dependency rule

Cross-subsystem coupling prefers **facades and flags** over deep imports. New reverse edges require an ADR.

---

## 6. Extension points

Future work may only land at these insertion points. New engines/layers need an ADR.

| Extension | Approved insertion point | Forbidden approach |
|-----------|--------------------------|--------------------|
| **Understanding → ranking assist (Phase 1 shadow)** | After DFP candidates / inside `assemble_evidence` merge; log `understanding_trace`; flag OFF by default | Rewriting QueryPlanner; replacing DFP |
| **Understanding assist mode (Phase 2)** | Soft signal into DocumentScorer / candidate merge; flag-gated | Admin weights UI |
| **Knowledge Memory (Epistemic)** | Memory Integration + Reasoning MemoryAssist; deepen claim quality | Parallel “memory” inside Retrieval |
| **Reasoning depth** | ReasoningService only | Prompt hacks in Generation as “reasoning” |
| **Knowledge Graph** | Optional adapter under `knowledge_understanding/adapters/` behind Protocol | Graph as public API or product center |
| **Fact validation** | Reasoning self-eval / sufficiency + Memory tensions | Hardcoded fact tables per tenant |
| **Agent tools** | Executive-authorized tool calls; never bypass Reasoning policy | Tools that write Memory without Integration |
| **Conversation memory** | Executive/session operational state; not epistemic claims | Storing chat as site knowledge |
| **Personalization** | Executive/session policy; tenant-safe; no per-tenant code forks | Tenant-specific ranking modules |
| **Incremental Understanding rebuild** | `UnderstandingRebuildService` / Builder | Ad-hoc SQL in SI apply |
| **ANN / scale for concepts** | Normalizer / Store / adapter internals | Changing Protocol to expose vectors |
| **Active acquisition** | Epistemic Maintenance + Indexing Gateway | Nightly “re-tune boosts” jobs |

---

## 7. Architecture invariants

These must never be violated:

1. **Planner plans. Retrieval retrieves. Evidence prepares. PromptBuilder renders. Generation generates.**
2. **Understanding understands.** Callers never depend on graph/index internals.
3. **Epistemic Memory is the sole owner of claim truth.** SI and Understanding do not replace it.
4. **No subsystem performs another’s responsibility.**
5. **Retrieval is a tool inside evidence assembly — not the product center.**
6. **Zero Hardcode:** no industry/bank/product/document-type intelligence tables in understanding or retrieval paths.
7. **No admin retrieval tuning** as a product surface (weights, priorities, thresholds, classification UIs). Modes only (e.g. Automatic / Fast / Balanced / High Precision).
8. **Shadow before influence:** Memory assist and Understanding assist stay advisory/shadow until measured and flag-gated.
9. **Diagnostics never mutate knowledge and never auto-tune cognition in v1.**
10. **Executive is the only global chat policy authority** when the Executive flag is ON.
11. **Reasoning must not write Memory** on the chat path.
12. **SI rebuilds Understanding; humans do not hand-edit ontologies.**
13. **Feature flags are defined in the canonical registry** (`feature_flags.py`); no shadow flag systems.
14. **Removed legacy must not return** (`intent_scorer`, `ranking.py` boost maps, `document_type_boost` in fuse, URL career heuristics as intelligence, etc.).
15. **New cognitive engines/layers require an ADR** — execution over invention.
16. **Representation changes inside Understanding do not change the Protocol.**
17. **Cache invalidation obeys `knowledge_version` / `memory_version`** — no silent stale truth.
18. **Fail-open on advisory paths** (Memory assist, Understanding rebuild soft-fail) must not corrupt SI or chat availability.

---

## 8. Performance invariants

1. **Chat path must not load full Source text blobs** for Understanding rebuild or unrelated work; project columns.
2. **Streaming** remains the user-visible generation path when enabled; diagnostics must not block first token unduly.
3. **Background embeddings** use the background pool; interactive query embeddings must not be starved.
4. **Understanding rebuild** is serialized (advisory lock); soft-fails; must not fatally fail SI finalize.
5. **O(C²) concept merge** is acceptable only while concept cardinality stays site-MVP-scale; ANN/incremental required before large-tenant primary use — implemented at Understanding internals, not by redesigning chat.
6. **Snapshot prune** must never delete the latest ready Understanding snapshot due to error churn.
7. **In-process caches** must include version/namespace inputs (`cache_namespace_v2` / knowledge & memory versions) when enabled.
8. **No synchronous full-corpus re-embed on chat requests.**
9. **Latency budgets:** Understanding resolution target ≤ 20ms once loaded (MVP success criterion); chat total timeout governed by Settings — do not “fix quality” by removing timeouts.

---

## 9. SaaS invariants

1. **No tenant-specific code paths** (no `if tenant == bank_x`).
2. **No industry packs** as intelligence.
3. **Knowledge independence:** each deployment/corpus builds SI + Understanding + Memory from its own content.
4. **Configuration ≠ intelligence:** Settings may gate features and resource limits; they must not encode domain ontology.
5. **Tenant isolation (future multi-tenant):** knowledge artifacts must be partitionable by tenant/corpus without rewriting subsystems; do not embed tenant names in algorithms.
6. **Flag defaults are product decisions** recorded in migrations/registry — not per-customer forks.
7. **One codebase** serves all tenants; customization is data (SI/Understanding/Memory), not modules.

---

## 10. Code review checklist (merge gate)

Every PR must satisfy:

### Ownership & boundaries

- [ ] Owning subsystem identified and matches this contract  
- [ ] No new responsibility split across two owners  
- [ ] No import violating §5  
- [ ] No frozen RAG stage redesign (Planner / DFP / EvidencePlanner / PromptBuilder / Generation) unless ADR  

### Intelligence policy

- [ ] No hardcoded industry/domain/product/document-type rules  
- [ ] No new admin retrieval sliders/weights/priority UIs  
- [ ] Inference preferred over config-as-intelligence  
- [ ] Understanding changes expose capabilities, not graph/storage APIs  

### Knowledge integrity

- [ ] Memory writes only through Memory Integration / Epistemic Memory owners  
- [ ] Understanding writes only through Understanding Store / Rebuild  
- [ ] SI remains per-source interpretation, not site-wide model  
- [ ] Diagnostics remain read-only  

### Evolution safety

- [ ] Extension uses an approved insertion point (§6) or ADR  
- [ ] Risky behavior flag-gated; default preserves production safety  
- [ ] Shadow/advisory before ranking influence  
- [ ] Rollback path clear (flag off or previous snapshot/version)  

### Performance & SaaS

- [ ] No full-table text loads on hot paths  
- [ ] No tenant-specific branches  
- [ ] Cache/version invalidation considered  
- [ ] Background vs interactive embedding pools respected  

### Verification

- [ ] Tests cover the owning subsystem behavior  
- [ ] `make test-backend` / relevant suite green for the change class  
- [ ] Release-impacting changes pass `make release-check` when required by release workflow  

---

## 11. Relationship to existing constitution docs

| Document | Relationship |
|----------|----------------|
| `COGNITIVE_ARCHITECTURE.md` | Cognitive ontology — frozen |
| `KNOWLEDGE_OS_ARCHITECTURE_v1.md` | Subsystem responsibility map — frozen; this contract operationalizes live owners |
| `RFC-0001` / `RFC-0002` | Product identity & active acquisition — frozen |
| `ENGINEERING_MANIFEST.md` | Zero Hardcode / Understanding-first — binding |
| `DEVELOPMENT_CHARTER.md` | Execution phase discipline / ADR rules — binding |
| `SEMANTIC_UNDERSTANDING_MVP.md` | Understanding phased delivery — binding for KUL |
| `rag-v2.1` (`rag_contract.py`) | Operational stage names — binding for RAG path |
| This **Architecture Contract 1.0** | Merge-gate constitution for the completed foundation |

If documents disagree on a **cognitive** boundary, Knowledge OS v1 wins.  
If they disagree on **live operational owners** of the RAG path, this contract + `rag_contract.py` win until an ADR migrates them.

---

## 12. Final architect review (five-year seal)

### Clarifications added by this freeze

- Split **Understanding Store** vs **Epistemic Memory** under “Knowledge Store” so five-year Memory work cannot be confused with concept-index snapshots.  
- Named **forbidden reverse imports** (Understanding ↛ DFP; Diagnostics ↛ Memory writes).  
- Locked **Phase 0 vs Phase 1** Understanding insertion so “available API” is not mistaken for ranking authority.  
- Restated **Executive / Reasoning / Language** as binding even when reviewers think only in RAG stages.  
- Locked **soft-fail / fail-open** rules so SaaS availability cannot be sacrificed to advisory subsystems.

### Dangerous dependencies explicitly forbidden

- Ranking ← Diagnostics feedback loops  
- Generation ← Retrieval  
- Retrieval ← Memory/Understanding writes  
- Tenant forks / industry modules  
- Graph as public contract  

### Signing statement

I would personally sign this Architecture Contract 1.0 as the permanent foundation of the platform:

- The cognitive model remains Knowledge OS, not RAG-as-product.  
- The operational RAG path is frozen as a successful tool with clear stage owners.  
- Understanding is a capability layer with SI-driven rebuild and representation freedom.  
- Epistemic Memory remains sole claim truth.  
- Zero Hardcode and no-admin-tuning remain non-negotiable.  
- Evolution has named insertion points; everything else requires an ADR.

**Signed:** Principal Software Architect  
**Document:** Architecture Contract 1.0  
**Action for engineers:** Comply on every PR. Do not reopen without ADR.

---

*End of Architecture Contract 1.0*
