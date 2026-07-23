# Knowledge OS Architecture Specification v1.0

**Status:** Architecture contract (cognitive model frozen for v1)  
**Audience:** Engineering team  
**Cognitive sources:** `COGNITIVE_ARCHITECTURE.md`, `RFC-0001-KNOWLEDGE-OS-CORE.md`, `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md`  
**Constraint:** No implementation, storage technology, schemas, or APIs in this document

This specification converts the frozen cognitive model into **subsystem responsibilities, boundaries, events, and lifecycles**. Engineers may choose any implementation technology if it respects this contract.

---

## Document map

| Part | Content |
|------|---------|
| 1 | System overview |
| 2 | Responsibility map |
| 3 | Event model |
| 4 | Lifecycles |
| 5 | Executive |
| 6 | Epistemic Memory |
| 7 | Interaction diagrams |
| 8 | Engineering principles |
| 9 | Migration plan (current → target) |
| 10 | MVP implementation order |

---

# PART 1 — SYSTEM OVERVIEW

## 1.1 What the Knowledge OS is (engineering view)

The Knowledge OS is a **multi-subsystem platform** that:

1. **Senses** informative content from websites (observations)  
2. **Interprets** observations into attributed claims  
3. **Maintains** Epistemic Memory (claims, beliefs, gaps, tensions, agenda)  
4. **Reasons** about user information needs against memory  
5. **Maintains itself** via epistemic tension reduction (active acquisition)  
6. **Speaks** through Language when self-evaluation permits  
7. **Coordinates** all of the above through an Executive  

Chat is one **interface**. Indexing is one **sensing channel**. Vector search is one **evidence assembly tool** — not the product.

## 1.2 Subsystem inventory (v1)

Twelve subsystems. Fewer would blur cognitive boundaries; more would over-engineer.

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXECUTIVE                                │
│              (coordination, policy, refusal authority)           │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
    ┌────────▼────────┐              ┌───────▼────────┐
    │   REASONING     │              │   EPIS TEMIC    │
    │  (stateless)    │◄────────────►│   MAINTENANCE   │
    └────────┬────────┘              └───────┬────────┘
             │                               │
             │         ┌─────────────────────▼─────────────┐
             │         │        EPIS TEMIC MEMORY           │
             └────────►│   (sole owner of knowledge state)  │
                       └─────────▲──────────────▲───────────┘
                                 │              │
              ┌──────────────────┘              └──────────────────┐
              │                                                    │
    ┌─────────▼──────────┐                              ┌──────────▼─────────┐
    │ CLAIM EXTRACTION   │                              │ OBSERVATION         │
    │ (Knowledge         │                              │ PROCESSING          │
    │  Intelligence)     │                              │                     │
    └─────────▲──────────┘                              └──────────▲─────────┘
              │                                                    │
              │              ┌──────────────────┐                  │
              └──────────────│ MEMORY INTEGRATION│──────────────────┘
                             │ (claim revision)  │
                             └─────────▲─────────┘
                                       │
                             ┌─────────┴─────────┐
                             │ EVIDENCE ASSEMBLY │◄── tool, not core
                             └─────────▲─────────┘
                                       │
    ┌──────────────┐  ┌────────────────┴───┐  ┌─────────────┐
    │   LANGUAGE   │  │  INDEXING GATEWAY   │  │  SCHEDULER  │
    │ (presentation)│  │  (world interface)  │  │  (triggers) │
    └──────────────┘  └─────────────────────┘  └─────────────┘
              ▲                    ▲
              │         ┌────────┴────────┐
              │         │   DIAGNOSTICS    │ (read-only)
              │         │   ANALYTICS      │ (aggregates)
              └─────────┴──────────────────┘
```

### Why each subsystem exists

| Subsystem | Cognitive responsibility | Why separate |
|-----------|-------------------------|--------------|
| **Executive** | Decide what runs next; arbitrate goals; authorize refusal | No other subsystem should own global policy |
| **Epistemic Memory** | Hold all knowledge state | Single source of epistemic truth |
| **Observation Processing** | Turn world artifacts into immutable observations | Sensing ≠ knowing |
| **Claim Extraction** | Propose attributed claims from observations | Interpretation ≠ storage |
| **Memory Integration** | Match, merge, revise claims; update beliefs | Revision logic centralized |
| **Epistemic Maintenance** | Surface tensions; maintain agenda; plan investigations | Active learning ≠ passive ingest |
| **Reasoning** | Resolve information need → belief state → speech act | Thinking ≠ speaking ≠ storing |
| **Evidence Assembly** | Gather observation text/evidence bundles on demand | Tool for Reasoning when memory alone insufficient |
| **Language** | Render belief states as natural language | Presentation ≠ cognition |
| **Indexing Gateway** | Execute world actions (fetch, crawl, re-read) | World I/O ≠ memory |
| **Scheduler** | Time-based triggers to Executive | Clock ≠ mind |
| **Diagnostics** | Human-readable traces of cognitive events | Observers must not mutate state |
| **Analytics** | Epistemic health aggregates | Long-horizon measurement ≠ real-time cognition |

### Deliberately merged (not separate subsystems)

| Rejected name | Merged into | Reason |
|---------------|-------------|--------|
| **Planner** | Epistemic Maintenance + Executive | Planning investigations = maintenance; budget = executive |
| **Curiosity Engine** | Epistemic Maintenance | Curiosity is policy over tensions, not a store |
| **Retrieval Engine** | Evidence Assembly | Retrieval is a tool, not architecture center |
| **Knowledge Graph** | Projection inside Memory (optional view) | Not cognitive core per v1 model |
| **Source Intelligence** (as product name) | Claim Extraction | Reframes “smart documents” as “claim proposals” |
| **Knowledge Profile** (rules) | **Deprecated** — not in target architecture | Manual ontology violates v1 cognitive model |
| **Cache** | Cross-cutting infrastructure | Not a cognitive subsystem; obeys Memory versioning |

### External interfaces (not subsystems)

- **Chat** — invokes Executive with `ReasoningRequested`  
- **Search** — invokes Reasoning + Evidence Assembly directly via Executive  
- **Admin dashboard** — reads Diagnostics + Analytics; must not mutate Memory in v1 target  

---

# PART 2 — RESPONSIBILITY MAP

## 2.1 Executive

| | |
|--|--|
| **Mission** | Coordinate all workflows; enforce budgets; resolve competing goals; authorize answer/refusal/defer |
| **Inputs** | User requests, scheduler ticks, maintenance completion, integration outcomes, reasoning outcomes |
| **Outputs** | Commands to subsystems; final response authorization; session/workflow state (operational, not epistemic) |
| **Internal state** | Workflow sessions, investigation budgets, feature flags (operational only) |
| **Owns** | Orchestration policy, concurrency limits, refusal authority |
| **Must never own** | Claims, beliefs, tensions, observations, natural language answers |

## 2.2 Epistemic Memory

| | |
|--|--|
| **Mission** | Sole authoritative store of epistemic state for a site |
| **Inputs** | Integration commands, maintenance updates, read queries |
| **Outputs** | Memory snapshots/views, revision confirmations, read models for Reasoning |
| **Internal state** | Observations (refs), claims, evidence links, belief states, gaps, tensions, agenda, concept regions, revision history |
| **Owns** | All knowledge state |
| **Must never own** | Crawl queues, LLM prompts, user sessions, raw website files as cognitive objects |

## 2.3 Observation Processing

| | |
|--|--|
| **Mission** | Convert fetched artifacts into immutable **Observation** records |
| **Inputs** | Raw page/file content, fetch metadata, structural signals (links, headings) |
| **Outputs** | `ObservationAdded` events |
| **Internal state** | Extraction profiles (operational), dedup keys |
| **Owns** | Observation normalization pipeline |
| **Must never own** | Claims, beliefs, ranking, answers |

## 2.4 Claim Extraction (Knowledge Intelligence)

| | |
|--|--|
| **Mission** | Propose **candidate attributed claims** and evidence links from observations |
| **Inputs** | Observations, optional memory context (existing claims for matching hints) |
| **Outputs** | `ClaimProposed`, `EvidenceProposed` events (not yet integrated) |
| **Internal state** | Extraction models/prompts (operational) |
| **Owns** | Interpretation quality |
| **Must never own** | Final claim truth in memory (only proposals); must not mutate integrated memory directly |

## 2.5 Memory Integration

| | |
|--|--|
| **Mission** | Integrate proposals into memory: match, merge, split, conflict, supersede; update beliefs; surface tensions |
| **Inputs** | Claim/evidence proposals, `ObservationAdded` |
| **Outputs** | `ClaimIntegrated`, `BeliefRevised`, `ConflictDetected`, `TensionOpened`, `TensionResolved`, `KnowledgeUpdated` |
| **Internal state** | Integration policies (operational); matching thresholds |
| **Owns** | Revision semantics |
| **Must never own** | Investigation execution; user-facing language |

*Note:* May be implemented as internal module inside Memory service, but responsibilities remain distinct.

## 2.6 Epistemic Maintenance

| | |
|--|--|
| **Mission** | Detect/sustain tensions; maintain Epistemic Agenda; prioritize investigation hypotheses |
| **Inputs** | Memory tension field, reasoning stress signals, integration events |
| **Outputs** | `AgendaUpdated`, `InvestigationPlanned`, investigation requests to Executive |
| **Internal state** | Priority scores, futility estimates, agenda item lifecycle |
| **Owns** | What should be learned next |
| **Must never own** | Fetch/crawl execution; claim integration; answers |

## 2.7 Reasoning

| | |
|--|--|
| **Mission** | Interpret information need; activate memory; form belief state; choose speech act; self-evaluate |
| **Inputs** | User question, memory read views, optional evidence bundles |
| **Outputs** | `ReasoningCompleted` (belief state, speech act, self-eval, stress signals) |
| **Internal state** | **None epistemic** — must be stateless across requests |
| **Owns** | Inference over memory for a single request |
| **Must never own** | Memory mutations; natural language generation; crawl decisions |

## 2.8 Evidence Assembly

| | |
|--|--|
| **Mission** | On demand, assemble **evidence bundles** (observation text spans + metadata) for Reasoning |
| **Inputs** | Evidence requests from Reasoning/Executive (claim IDs, regions, hooks) |
| **Outputs** | Evidence bundles (not answers) |
| **Internal state** | Sensory indexes (e.g. chunk index) — **operational artifacts**, not epistemic memory |
| **Owns** | Efficient lookup of observation content |
| **Must never own** | Belief revision; ranking as primary architecture; answer generation |

## 2.9 Language

| | |
|--|--|
| **Mission** | Render authorized belief state + speech act into user language |
| **Inputs** | Approved `ReasoningCompleted` payload, style/locale policy |
| **Outputs** | `AnswerGenerated` text, citation presentation |
| **Internal state** | Prompt templates (operational) |
| **Owns** | Fluency and format |
| **Must never own** | Epistemic decisions; memory access beyond provided bundle |

## 2.10 Indexing Gateway

| | |
|--|--|
| **Mission** | Execute world I/O: fetch URLs, crawl frontiers, re-read sources per investigation plan |
| **Inputs** | Investigation commands from Executive |
| **Outputs** | Raw artifacts → Observation Processing |
| **Internal state** | Crawl frontier, fetch queues, robots policy |
| **Owns** | World access mechanics |
| **Must never own** | Claims, tensions, reasoning |

## 2.11 Scheduler

| | |
|--|--|
| **Mission** | Emit time-based triggers (maintenance cycle, re-index, consolidation) |
| **Inputs** | Schedules, operational config |
| **Outputs** | `MaintenanceDue`, `IndexCycleDue` to Executive |
| **Internal state** | Timers |
| **Owns** | When to ask Executive to act |
| **Must never own** | Prioritization logic; epistemic state |

## 2.12 Diagnostics

| | |
|--|--|
| **Mission** | Record and project cognitive events for humans (semantic decisions, not score dumps) |
| **Inputs** | All domain events (subscribe) |
| **Outputs** | Trace views, debug payloads |
| **Internal state** | Trace storage (operational) |
| **Owns** | Explainability projection |
| **Must never own** | Memory; must not feed back into Reasoning automatically in v1 |

## 2.13 Analytics

| | |
|--|--|
| **Mission** | Aggregate epistemic health metrics over time |
| **Inputs** | Events + Diagnostics + Memory health snapshots |
| **Outputs** | Dashboards, trend reports, stress hotspots |
| **Internal state** | Aggregates |
| **Owns** | Long-horizon measurement |
| **Must never own** | Real-time orchestration; must not auto-tune cognition in v1 |

---

# PART 3 — EVENT MODEL

Events are the **contract between subsystems**. They carry payloads defined in cognitive terms (claim, tension, belief state), not storage rows.

## 3.1 Event catalog

### Observation & extraction

| Event | Emitter | Consumers | State change |
|-------|---------|-----------|--------------|
| `ObservationAdded` | Observation Processing | Memory Integration, Diagnostics | New immutable observation registered |
| `ClaimProposed` | Claim Extraction | Memory Integration, Diagnostics | None in authoritative memory yet |
| `EvidenceProposed` | Claim Extraction | Memory Integration | None yet |

### Memory integration

| Event | Emitter | Consumers | State change |
|-------|---------|-----------|--------------|
| `ClaimIntegrated` | Memory Integration | Maintenance, Diagnostics, Analytics | Claim created/updated/merged/split |
| `EvidenceLinked` | Memory Integration | Maintenance, Diagnostics | Support/conflict/duplicate link added |
| `BeliefRevised` | Memory Integration | Maintenance, Diagnostics, Analytics | Belief state recalculated for cluster |
| `ConflictDetected` | Memory Integration | Maintenance, Executive (signal) | Conflict record opened |
| `ConflictResolved` | Memory Integration | Maintenance, Diagnostics | Conflict closed (merged, scoped, or acknowledged) |
| `ClaimSuperseded` | Memory Integration | Maintenance, Diagnostics | Lineage updated; old claim demoted |
| `RegionUpdated` | Memory Integration | Diagnostics | Concept region membership changed |
| `KnowledgeUpdated` | Memory Integration | Analytics, Cache invalidation | Memory version bumped |

### Maintenance

| Event | Emitter | Consumers | State change |
|-------|---------|-----------|--------------|
| `GapOpened` / `GapClosed` | Memory Integration or Maintenance | Maintenance, Diagnostics | Gap lifecycle |
| `TensionOpened` | Memory Integration / Maintenance | Maintenance, Executive, Diagnostics | Tension added to field |
| `TensionResolved` | Maintenance / Integration | Diagnostics, Analytics | Tension removed/downgraded |
| `AgendaUpdated` | Epistemic Maintenance | Executive, Diagnostics | Agenda item add/priority change |
| `InvestigationPlanned` | Epistemic Maintenance | Executive, Diagnostics | Hypothesis ready for execution |
| `InvestigationCompleted` | Executive / Indexing Gateway | Maintenance, Diagnostics | Outcome for agenda item |
| `MaintenanceCycleCompleted` | Executive | Analytics, Diagnostics | Cycle summary |

### Reasoning & response

| Event | Emitter | Consumers | State change |
|-------|---------|-----------|--------------|
| `ReasoningRequested` | Interface → Executive | Executive, Diagnostics | Workflow started |
| `EvidenceRequested` | Reasoning → Executive | Evidence Assembly | None in memory |
| `EvidenceBundleReady` | Evidence Assembly | Reasoning | None in memory |
| `ReasoningCompleted` | Reasoning | Executive, Maintenance, Diagnostics | Belief state + speech act + self-eval (ephemeral until Language) |
| `AnswerAuthorized` | Executive | Language, Diagnostics | Refusal or proceed |
| `AnswerGenerated` | Language | Interface, Diagnostics, Analytics | User-visible text |
| `ReasoningStress` | Reasoning | Maintenance | Boost tension priorities (no memory mutation) |

### Operations

| Event | Emitter | Consumers | State change |
|-------|---------|-----------|--------------|
| `MaintenanceDue` | Scheduler | Executive | Triggers maintenance workflow |
| `IndexCycleDue` | Scheduler | Executive | Triggers index/crawl workflow |
| `DiagnosticsRecorded` | Diagnostics | (storage) | Trace append |

## 3.2 Event rules

1. **Only Memory Integration mutates authoritative epistemic state** (via Memory service API).  
2. **Claim Extraction never emits `ClaimIntegrated`** — only proposals.  
3. **Reasoning never emits `BeliefRevised`** — it may emit `ReasoningStress`.  
4. **Diagnostics subscribes to all; emits nothing that mutates Memory.**  
5. **`KnowledgeUpdated` carries memory version** — all caches must respect it.

---

# PART 4 — LIFECYCLES

## 4.1 Website indexing (initial)

```
Scheduler/Admin → Executive: start index
Executive → Indexing Gateway: crawl/fetch plan
Indexing Gateway → Observation Processing: raw artifacts
Observation Processing → Memory Integration: ObservationAdded
Memory Integration → Claim Extraction: (async) extract from new observations
Claim Extraction → Memory Integration: ClaimProposed / EvidenceProposed
Memory Integration: integrate → BeliefRevised, TensionOpened, KnowledgeUpdated
Executive → Epistemic Maintenance: post-batch tension scan
Maintenance → Executive: AgendaUpdated (optional investigations)
Executive → Indexing Gateway: execute top investigations (budgeted)
... loop until agenda equilibrium or budget exhausted ...
Executive → Diagnostics: cycle summary
```

## 4.2 Page update (re-index single source)

```
Indexing Gateway fetches changed artifact
Observation Processing: new ObservationAdded (new observation event; prior kept)
Claim Extraction: proposals from delta
Memory Integration: match → strengthen | supersede | conflict
BeliefRevised, possibly TensionOpened or TensionResolved
KnowledgeUpdated
Maintenance: re-evaluate affected agenda items
```

## 4.3 Knowledge revision (passive)

Triggered by any integration. No Executive required unless tension crosses action threshold.

```
ClaimProposed → match engine → ClaimIntegrated
→ recompute affected belief states
→ update gaps/tensions
→ emit BeliefRevised, KnowledgeUpdated
```

## 4.4 User question

```
User → Interface: question
Interface → Executive: ReasoningRequested
Executive → Reasoning: run (with memory read lease)
Reasoning → Memory: read views (claims, beliefs, gaps for activated regions)
Reasoning: interpret need → activate regions → form belief state
If insufficient → Reasoning → Executive: EvidenceRequested
Executive → Evidence Assembly: bundle
Evidence Assembly → Reasoning: EvidenceBundleReady
Reasoning: self-evaluate → ReasoningCompleted + optional ReasoningStress
Executive: authorize speech act (answer | refuse | qualify)
If authorized → Language → AnswerGenerated
If ReasoningStress → Maintenance: agenda priority boost (async)
Diagnostics: full trace
```

## 4.5 Maintenance cycle (active)

```
Scheduler → Executive: MaintenanceDue
Executive → Maintenance: run tension scan + agenda ranking
Maintenance → Executive: InvestigationPlanned (within budget)
Executive → Indexing Gateway OR Claim Extraction (re-interpret): execute
Results → Observation Processing / Integration path
Maintenance: evaluate tension reduction → TensionResolved or futility++
Executive: MaintenanceCycleCompleted
```

## 4.6 Conflict resolution

```
Memory Integration: ConflictDetected
Maintenance: enqueue agenda item (hypothesis: adjudication observation)
Executive: plan investigation OR defer if non-blocking
Integration: ConflictResolved via scope split | supersession | acknowledged irreconcilable
BeliefRevised with epistemic status = Conflicting if unresolved
Language must use conflict speech act if Reasoning hits unresolved conflict
```

## 4.7 Learning cycle (composite)

Passive + active rhythms from RFC-0002:

```
[Passive] observations integrate continuously
[Active] Executive runs maintenance on schedule + stress triggers
[Feedback] ReasoningStress boosts agenda
[Closure] Maintenance closes unresolvable gaps
[Consolidation] Memory Integration merges/splits regions (scheduled)
```

---

# PART 5 — EXECUTIVE

## 5.1 Why Executive is mandatory

Without Executive, subsystems collide:

- Reasoning fetches evidence directly → bypasses refusal policy  
- Maintenance crawls unbounded → no budget  
- Language generates before self-evaluation → dishonest answers  
- Integration and extraction race → inconsistent memory  

Executive is the **only subsystem with global authority**.

## 5.2 Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Workflow orchestration** | Start/end indexing, Q&A, maintenance cycles |
| **Budget enforcement** | Investigation limits, LLM/token limits, concurrency |
| **Goal arbitration** | User latency vs maintenance depth vs index progress |
| **Refusal authority** | Only Executive authorizes `AnswerGenerated` or refusal |
| **Investigation dispatch** | Routes planned investigations to Indexing Gateway or re-interpret path |
| **Memory version gate** | Ensures Reasoning reads consistent memory snapshot |
| **Degradation policy** | Under load: defer maintenance, shorten evidence assembly, refuse vs hallucinate |

## 5.3 Decisions Executive makes

| Question | Decider |
|----------|---------|
| What happens next? | **Executive** |
| Who coordinates Reasoning? | **Executive** |
| Who schedules maintenance? | **Scheduler triggers; Executive commits** |
| Who prioritizes investigations? | **Maintenance ranks; Executive allocates budget** |
| Competing user request vs maintenance? | **Executive** (policy: user-facing latency priority unless critical tension) |
| When to refuse answer? | **Reasoning recommends; Executive authorizes** |

## 5.4 What Executive is not

- Not a reasoning engine (does not form beliefs)  
- Not a memory store  
- Not a crawler  
- Not an LLM wrapper  

Executive **coordinates**; it does not **think**.

## 5.5 Operational session state

Executive may hold:

- Request ID, workflow phase, deadlines  
- Investigation budget consumed this cycle  
- Feature flags  

Executive must **not** hold claims, beliefs, or tensions — always read from Memory.

---

# PART 6 — EPIS TEMIC MEMORY

## 6.1 Role

Memory is the **heart** — single authoritative epistemic store per site (per tenant in future).

## 6.2 Responsibilities

- Persist and serve: observations (refs), claims, evidence links, belief states, gaps, tensions, agenda, regions, revision history  
- Enforce integration semantics (merge, split, supersede, conflict)  
- Expose **read views** optimized for Reasoning (region activation, claim clusters, epistemic status)  
- Bump **memory version** on material change  

## 6.3 Guarantees

| Guarantee | Meaning |
|-----------|---------|
| **Single writer** | Only Memory Integration path mutates authoritative state |
| **Observation immutability** | Observations append-only; never edited |
| **Claim revisability** | Claims mutate through defined operations only |
| **Provenance** | Every claim traceable to evidence → observation |
| **Consistency** | Reasoning reads snapshot or versioned view — no torn reads |
| **Honest conflict** | Conflicting claims never silently collapsed |

## 6.4 Allowed mutations

- Add observation reference  
- Create/update/merge/split/supersede claims  
- Add/remove evidence links with role (support, conflict, duplicate, inferential)  
- Recompute belief states (derived cache)  
- Open/update/close gaps and tensions  
- Update agenda (via Maintenance commands authorized by Executive)  
- Update concept regions (emergent compression)  
- Append revision history entries  

## 6.5 Forbidden mutations

- Delete observations  
- Modify observation content  
- Create claims without evidence link or explicit inferential marker  
- Set belief state without claim delta  
- Delete conflict records without resolution type  
- Direct edit of tensions by Reasoning or Language  

## 6.6 Consistency rules

1. Belief states must recompute when constituent claims change.  
2. Tension must reference anchor claim(s) or region(s).  
3. Agenda items must reference tension ID.  
4. Supersession must preserve lineage.  
5. Closed-unresolvable gaps must not re-open without new hook.  

## 6.7 History rules

- Observations: immutable log  
- Claims: revision chain with supersession links  
- Belief states: optional historical snapshots for audit (derived)  
- Tensions/agenda: lifecycle log  

## 6.8 Ownership

| Entity | Owner |
|--------|-------|
| Epistemic state | Memory |
| Sensory indexes (chunk vectors) | Evidence Assembly (operational) |
| Raw HTML/files | Indexing Gateway / operational store (non-cognitive) |

---

# PART 7 — INTERACTION DIAGRAMS

## 7.1 User question (happy path)

```
User
  → Interface
  → Executive : ReasoningRequested
  → Reasoning
      ↔ Memory : read (regions, claims, beliefs, gaps)
      → Executive : ReasoningCompleted (answer speech act, self-eval pass)
  → Executive : AnswerAuthorized
  → Language : render
  → Interface → User
  ← Diagnostics (parallel subscribe)
```

## 7.2 User question (insufficient evidence → refuse)

```
User → Executive → Reasoning ↔ Memory
Reasoning → Executive : ReasoningCompleted (refusal speech act, self-eval fail)
Executive → Language : render refusal + explanation
Optional: ReasoningStress → Maintenance → AgendaUpdated
```

## 7.3 User question (needs evidence assembly)

```
User → Executive → Reasoning ↔ Memory
Reasoning → Executive : EvidenceRequested
Executive → Evidence Assembly
Evidence Assembly → Reasoning : EvidenceBundleReady
Reasoning → Executive : ReasoningCompleted
Executive → Language → User
```

## 7.4 New page indexed (passive learning)

```
Indexing Gateway → Observation Processing : ObservationAdded
→ Claim Extraction : proposals
→ Memory Integration : integrate
→ Events: ClaimIntegrated, BeliefRevised, KnowledgeUpdated
→ Maintenance : tension scan (async)
```

## 7.5 Maintenance investigation

```
Scheduler → Executive : MaintenanceDue
Executive → Maintenance : scan + rank
Maintenance → Executive : InvestigationPlanned
Executive → Indexing Gateway (fetch) OR re-interpret path
→ Observation Processing → Integration
Maintenance : TensionResolved? → update Agenda
Executive : MaintenanceCycleCompleted
```

## 7.6 Conflict surfaced

```
Memory Integration : ConflictDetected
→ Maintenance : agenda item
Executive : optional investigation
Integration : ConflictResolved OR epistemic status = Conflicting
Reasoning (later) : conflict speech act if user asks affected question
```

## 7.7 Diagnostics-only consumer

```
All subsystems → event bus → Diagnostics → Admin UI
(No return path to Memory or Reasoning in v1)
```

---

# PART 8 — ENGINEERING PRINCIPLES

Immutable rules for v1 implementation.

## 8.1 Boundary principles

1. **One epistemic writer.** Only Memory Integration mutates authoritative knowledge state.  
2. **Reasoning is stateless.** No cross-request epistemic cache inside Reasoning.  
3. **Language is presentation only.** No memory access except packaged payload.  
4. **Executive coordinates; it does not know.** No claims/beliefs in Executive state.  
5. **Evidence Assembly is a tool.** Reasoning requests; it does not own beliefs.  
6. **Observations are immutable.** Revise claims, not observations.  
7. **Extraction proposes; Integration disposes.**  
8. **Maintenance plans; Executive executes; Gateway fetches.**  
9. **Diagnostics observes only.** No feedback loop in v1.  
10. **Scheduler triggers; never prioritizes.**

## 8.2 Cognitive fidelity principles

11. **Claims before containers.** No subsystem treats pages as knowledge.  
12. **Tensions require anchors.** No investigation without hooks.  
13. **Refusal is first-class.** Authorized by Executive on Reasoning recommendation.  
14. **Conflict is visible.** Never average contradictions in Memory.  
15. **Memory version gates cache.** Any cache of answers/evidence respects `KnowledgeUpdated`.

## 8.3 Simplicity principles

16. **Merge before split.** Prefer fewer subsystems until pain proves separation.  
17. **Events over direct calls** for cross-subsystem coupling (allows incremental migration).  
18. **Read views over chatty queries.** Memory exposes Reasoning-optimized projections.  
19. **No cyclic ownership.** Dependency graph is DAG with Executive at top.  
20. **Deprecate, don’t duplicate.** Legacy retrieval path wraps into Evidence Assembly once.

## 8.4 Challenged defaults (accepted/rejected)

| Principle | Verdict |
|-----------|---------|
| “Memory is append-and-revise” | **Accepted** for observations and revision history; claims are revisable in place with lineage |
| “Analytics never influences cognition” | **Accepted for v1** — no auto-tuning from analytics |
| “Reasoning never mutates memory” | **Accepted** — stress signals via events only |
| Separate Memory Integration module | **Accepted** — distinct from Extraction even if same deployable unit initially |

---

# PART 9 — MIGRATION PLAN

Mapping **current implementation** → **target subsystem**.

| Current component | Disposition | Target | Why |
|-------------------|-------------|--------|-----|
| `IndexingService`, `CrawlerService`, workers | **Refactor** | Indexing Gateway + Observation Processing | Separate world I/O from observations |
| `SourceIntelligenceService`, LLM SI | **Refactor** | Claim Extraction | Reframe as claim proposals, not “source profiles” |
| `SourceIntelligenceGenerationService` | **Refactor** | Claim Extraction + Executive batch | Batch under Executive |
| Per-page SI JSON on `Source` row | **Replace** | Epistemic Memory (claims) | Claims are authoritative; SI JSON is transitional |
| `DocumentFirstRetrievalPipeline`, retrievers | **Refactor** | Evidence Assembly | Tool behind Executive, not chat entry |
| `RetrievalPipelineService` | **Split** | Executive + Reasoning + Evidence Assembly | Orchestration vs thinking vs lookup |
| `RagService`, `RagStreaming` | **Refactor** | Executive + Reasoning + Language | Remove retrieve-first identity |
| `QueryUnderstandingService` | **Keep** | Inside Reasoning | Aligns with information need interpretation |
| `SemanticCompatibilityScorer`, `DocumentScorer` | **Refactor** | Reasoning (evidence relevance) + Memory (belief fit) | Split structural compatibility vs epistemic state |
| `DocumentReranker`, `ExplanationBuilder` | **Keep** | Reasoning + Language/Diagnostics | Self-eval + explainability |
| `HybridRetrievalService` | **Deprecate** | Evidence Assembly (remove) | Test-only legacy |
| `KnowledgeProfileService`, presets, boost tables | **Deprecate** | — | Violates v1 cognitive model |
| `knowledge_profile_generation/*` | **Refactor** | Claim Extraction + Maintenance (tension surfacing) | Stop emitting boost rules |
| `CanonicalSourceService` | **Replace** | Memory authority model + Reasoning | No doc-type canonical |
| `ContextBuilder`, `PromptBuilder` | **Refactor** | Language + Evidence Assembly | Context = evidence bundle; prompt = presentation |
| `retrieval_cache`, `answer_cache` | **Refactor** | Infrastructure | Key on memory version |
| `AnalyticsService` | **Refactor** | Analytics | Shift to epistemic health metrics |
| Chat diagnostics components | **Refactor** | Diagnostics | Semantic traces |
| Settings boost knobs, profile editor UI | **Deprecate** | — | Admin provides URL + index only |
| `Chunk` / Qdrant index | **Keep** | Evidence Assembly sensory index | Operational, not cognitive |
| `Source` ORM | **Refactor** | Indexing Gateway operational metadata | Demote from knowledge object |

### Summary disposition counts

| Action | Count (approx.) |
|--------|-----------------|
| Keep (with minor moves) | 4 |
| Refactor | 18 |
| Split | 2 |
| Replace | 3 |
| Deprecate | 6 |
| Merge | 2 (hybrid into evidence; integration into memory module) |

---

# PART 10 — MVP IMPLEMENTATION ORDER

**Strategy:** Smallest sequence that **continuously improves** production while converging on architecture. Each phase delivers user-visible or operator-visible value. No big-bang rewrite.

---

## Phase 0 — Executive shell & boundaries

| | |
|--|--|
| **Goal** | Introduce Executive as orchestrator without changing answer quality |
| **Affected** | `RagService`, `RagStreaming` → thin Executive; document boundaries |
| **Benefit** | Single coordination point for later migration |
| **Risk** | Low — passthrough wrapper |
| **Compatibility** | 100% behavior parity |
| **Rollback** | Feature flag: direct Rag path |
| **Tests** | Parity tests: same answers for fixed query set |
| **Success** | All chat flows enter through Executive; no new features |

---

## Phase 1 — Diagnostics & legacy visibility

| | |
|--|--|
| **Goal** | Semantic diagnostics; mark legacy rule paths |
| **Affected** | Diagnostics, Chat debug UI, docs; deprecate notices on Knowledge Profile boosts |
| **Benefit** | Team sees tension between legacy and target |
| **Risk** | Low |
| **Compatibility** | Additive |
| **Rollback** | Hide new diagnostic panels |
| **Tests** | Diagnostics contain reasoning trace structure (stub fields OK) |
| **Success** | No production reliance on boost tables documented and tested |

---

## Phase 2 — Memory facade & version

| | |
|--|--|
| **Goal** | Epistemic Memory service with version counter; read-only views |
| **Affected** | New Memory module; `KnowledgeUpdated` event; cache namespace uses memory version |
| **Benefit** | Foundation for claims; cache correctness |
| **Risk** | Low — no chat change yet |
| **Compatibility** | Additive; SI JSON still written |
| **Rollback** | Memory version ignored by caches |
| **Tests** | Version bumps on integration events |
| **Success** | Memory read API serves empty/minimal claim set in shadow |

---

## Phase 3 — Observation + Claim pipeline (shadow)

| | |
|--|--|
| **Goal** | Observation Processing + Claim Extraction from indexed content; integrate in shadow |
| **Affected** | Indexing path, Claim Extraction (from SI), Memory Integration |
| **Benefit** | Real claims in memory; parallel to legacy |
| **Risk** | Medium — extraction quality |
| **Compatibility** | Legacy chat unchanged |
| **Rollback** | Disable integration writes |
| **Tests** | Claims produced for sample pages; provenance to observations |
| **Success** | Memory holds claims for ≥80% SI-enriched sources (internal metric) |

---

## Phase 4 — Tension surfacing (read-only)

| | |
|--|--|
| **Goal** | Epistemic Maintenance detects tensions; agenda read-only in admin |
| **Affected** | Maintenance module, Diagnostics dashboard |
| **Benefit** | “What should we learn next?” visible — RFC-0002 Phase 1 |
| **Risk** | Low if read-only |
| **Compatibility** | No crawl behavior change |
| **Rollback** | Hide tension UI |
| **Tests** | Conflict/support deficit fixtures produce tensions |
| **Success** | Operators see tensions with anchors and types |

---

## Phase 5 — Reasoning extraction

| | |
|--|--|
| **Goal** | Reasoning subsystem owns information need → belief state → self-eval; Evidence Assembly wraps current retrieval |
| **Affected** | Split from `RetrievalPipelineService`; Executive workflow |
| **Benefit** | Retrieval demoted to tool; reasoning testable in isolation |
| **Risk** | Medium — behavior regression |
| **Compatibility** | Flag-gated; legacy pipeline fallback |
| **Rollback** | Executive → legacy pipeline |
| **Tests** | Reasoning unit tests; parity suite on broad queries |
| **Success** | ReasoningCompleted drives answer; ReasoningStress emitted |

---

## Phase 6 — Memory-driven evidence selection

| | |
|--|--|
| **Goal** | Reasoning activates memory regions first; Evidence Assembly fills gaps |
| **Affected** | Reasoning, Evidence Assembly, Memory read views |
| **Benefit** | Answers cite claim-backed evidence; fewer wrong pages |
| **Risk** | Medium |
| **Compatibility** | Gradual; hybrid with vector fallback |
| **Rollback** | Fallback to vector-first assembly |
| **Tests** | Correct evidence for claim-specific questions |
| **Success** | Measurable improvement on offline eval set |

---

## Phase 7 — Active maintenance (budgeted)

| | |
|--|--|
| **Goal** | Executive runs investigations from agenda within budget |
| **Affected** | Maintenance, Executive, Indexing Gateway |
| **Benefit** | Autonomous gap reduction |
| **Risk** | Medium — crawl scope |
| **Compatibility** | Opt-in per site; default budget = 0 |
| **Rollback** | Disable maintenance execution |
| **Tests** | Tension resolves when target page fetched |
| **Success** | Blocking tension count decreases on test site |

---

## Phase 8 — Legacy deprecation

| | |
|--|--|
| **Goal** | Remove Knowledge Profile rules, boost tables, canonical doc-type, industry presets from production path |
| **Affected** | KnowledgeProfile*, CanonicalSourceService, settings UI |
| **Benefit** | RFC-0001 compliance |
| **Risk** | High — sites tuned on legacy |
| **Compatibility** | Requires Phases 5–7 live |
| **Rollback** | Legacy preset import (read-only) for one release |
| **Tests** | No industry preset in production path; generic fixtures only |
| **Success** | Admin surface = URL + index + understanding health |

---

## Phase diagram

```
Phase 0 Executive shell
  ↓
Phase 1 Diagnostics visibility
  ↓
Phase 2 Memory facade + version
  ↓
Phase 3 Claims pipeline (shadow)
  ↓
Phase 4 Tensions (read-only)
  ↓
Phase 5 Reasoning extraction ← critical pivot
  ↓
Phase 6 Memory-first evidence
  ↓
Phase 7 Active maintenance
  ↓
Phase 8 Legacy deprecation
```

**Do not start Phase 5 before Phase 3.** Reasoning without claims is hollow.  
**Do not start Phase 7 before Phase 4.** Active acquisition without tension visibility is blind.

---

# APPENDIX A — Cognitive ↔ Engineering glossary

| Cognitive (frozen) | Engineering subsystem |
|--------------------|----------------------|
| Observation | Observation Processing output |
| Attributed claim | Memory entity via Integration |
| Evidence link | Memory relation |
| Belief state | Memory derived cache |
| Concept region | Memory emergent index |
| Gap / tension | Memory + Maintenance |
| Epistemic Agenda | Maintenance state (stored in Memory) |
| Investigation hypothesis | Maintenance output |
| Information need | Reasoning input |
| Speech act | Reasoning output |
| Self-evaluation | Reasoning output |
| Sensory index | Evidence Assembly operational store |

---

# APPENDIX B — Document hierarchy

| Layer | Document |
|-------|----------|
| Cognitive (frozen v1) | `COGNITIVE_ARCHITECTURE.md`, `RFC-0002` |
| Product identity | `RFC-0001`, `KNOWLEDGE_INTELLIGENCE_ENGINE.md` |
| **Engineering contract (this doc)** | `KNOWLEDGE_OS_ARCHITECTURE_v1.md` |
| Gap analysis | `ARCHITECTURE_REVIEW_KNOWLEDGE_OS.md` |
| Legacy software path | `SEMANTIC_UNDERSTANDING_MVP.md` (superseded by this spec — reframe during Phase 2+) |

**When cognitive and engineering conflict, cognitive wins.** When engineering phases conflict with simplicity, prefer the phase order in Part 10.

---

# APPENDIX C — Explicit non-goals for v1 architecture

- Multi-site federated memory  
- Autonomous agents / tool calling beyond fetch & re-interpret  
- Analytics-driven auto-tuning  
- User-editable ontology or tension rules  
- Real-time collaborative memory editing  
- Graph database as system of record  

These may come later; they are **not** subsystems in v1.

---

**End of Knowledge OS Architecture Specification v1.0**
