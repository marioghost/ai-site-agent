# Cognitive Architecture of the Knowledge OS

**Type:** Research document — thinking architecture, not software architecture  
**Status:** Foundational design review  
**Constraint:** No implementation, schemas, APIs, or storage technology assumptions

This document defines what the system **knows**, **how it thinks**, and **how knowledge changes** — independent of RAG, graphs, Source Intelligence, or any current codebase.

---

## Preamble: What we are actually building

We are not building a system that **stores websites**.

We are building a system that **forms and maintains opinions about what a website communicates** — with calibrated uncertainty, revisable conclusions, and explicit ignorance.

That is a **cognitive system**, not a search index.

The failure mode of most “knowledge platforms” is category error: they optimize **access to text** and call it **understanding**. Text access is necessary. It is not sufficient. Understanding requires an internal model of *what is being claimed*, *how strongly it is supported*, *what conflicts*, and *what is absent*.

Your instinct to move beyond documents, retrieval, and graphs is correct.  
Your instinct that **beliefs** may be the right primitive is partially correct — but incomplete without a grounding layer beneath beliefs. This document proposes a fuller epistemic model and stress-tests your assumptions.

---

## 1. What is Knowledge?

### The wrong candidates (and why)

| Candidate | Why it fails as the atomic unit |
|-----------|--------------------------------|
| **Document / page** | A container, not knowledge. Humans do not “know pages.” |
| **Chunk** | A retrieval artifact. Meaningless without interpretive context. |
| **Embedding** | A coordinate in similarity space, not knowledge. It has no propositional content. |
| **Entity** | A referent, not knowledge. “Premium Card” is a pointer; knowledge is what is claimed *about* it. |
| **Concept** | A cluster label — useful, but too coarse to be atomic. “Credit products” is not one thing; it is a region of many claims. |
| **Fact** | Implies truth. The engine cannot know truth — only what the **site asserts** and how well that assertion is supported. |

### The smallest unit: the **Attributed Claim**

The smallest knowledge-bearing unit inside this system should be:

> **An attributed claim**: a semantic proposition extracted from the world (a website), tied to evidence, with explicit scope and epistemic status.

Examples (internal, not user-facing):

- *“This site presents ‘Premium Card’ as a credit product offering.”*  
  — supported by evidence E₁, E₂; confidence 0.82; scope: product catalog region

- *“Annual fee for Premium Card is 500 UAH.”*  
  — supported by E₃ only; confidence 0.55; scope: single product detail page

- *“The site positions itself as a retail bank.”*  
  — supported by many weak + strong sources; confidence 0.91

A **claim** is not necessarily true. It is **what the engine takes the site to be saying**, with metadata about how that interpretation was formed.

### Where beliefs, concepts, and evidence fit

```
Evidence  →  grounds  →  Claim  →  aggregates into  →  Concept region
                              ↓
                         Belief state (epistemic stance over a claim cluster)
```

- **Evidence** is not knowledge. It is the **trace** that justifies claims (ultimately traceable to observations, but the engine should reason about evidence, not raw HTML).
- **Concepts** are **emergent regions** in claim-space — stable clusters that humans would name (“credit products”, “shipping policy”). They are not primitives; they are **compression** over many claims.
- **Beliefs** are **not inputs** — they are **consolidated epistemic states** over one or more related claims (see Section 4).

### Reasoning summary

Knowledge in this system is **not information storage**.  
It is **a living set of attributed claims, organized by emergent structure, each with an epistemic status**.

If you must name one primitive: **Attributed Claim**.  
Beliefs are derived. Concepts are compressed. Documents are forgotten.

---

## 2. What does the system actually know?

After indexing 10,000 pages, the engine should **not** internally resemble a library of 10,000 items.

A human expert who read the site would not recite URLs. They would hold something like:

### 2.1 A **claim landscape**

Thousands (or tens of thousands) of attributed claims — not sentences copied from pages, but **interpreted propositions** with:

- what is being asserted
- about what (entities, topics — emergent, not predefined)
- in what role (definition, enumeration, comparison, procedure, contact, legal disclaimer…)
- with what scope (site-wide, section-specific, time-bound, product-specific)

### 2.2 An **evidence economy**

For each claim, the engine knows:

- which observations support it
- whether sources are independent or duplicates
- whether evidence is primary (explicit statement) or inferential (implied)
- whether a single marketing page or multiple independent sections agree

The engine knows **provenance without memorizing pages** — like a scientist who remembers *“this conclusion rests on three independent experiments”* without re-reading the lab notebooks unless challenged.

### 2.3 **Emergent concept regions**

Not an ontology. Not “product_page.” Regions like:

- “what this organization is”
- “what products/services exist”
- “how to contact / get support”
- “rules and constraints”
- “pricing and rates”

These regions are **discovered** by density and connectivity of claims — not assigned by industry template.

### 2.4 **Authority and centrality**

The engine knows, for each region:

- which claims are **central** (many connections, high corroboration)
- which are **peripheral** (mentioned once, weakly supported)
- which sources behave as **canonical explainers** for a region (not because of URL pattern — because of evidential role)

### 2.5 **Ignorance map**

Equally important: what the engine **does not know**:

- regions with no claims
- regions with only weak single-source claims
- questions the site **cannot** answer given indexed content
- boundaries of enumeration (“these are the products *the site mentions*” vs “all products that exist in the world”)

A system that only stores what it found is **incomplete intelligence**. A system that maps its own ignorance is **trustworthy intelligence**.

### 2.6 **Conflict and revision state**

Where claims disagree:

- “Free account” on page A vs “Monthly fee applies” on page B
- Old press release vs current product page

The engine knows **conflict exists** — not necessarily which is “true.”

### 2.7 What it should **not** “know”

Internally, after sufficient consolidation:

- It should **not** maintain 10,000 page objects as cognitive entities
- It should **not** “know” document types, boost values, or retrieval scores
- It should **not** treat embeddings as knowledge — only as one indexing sense for similarity

**In one sentence:**  
After indexing, the engine knows **a structured, uncertain, revisable model of what the website communicates**, organized by emergent meaning — not by filesystem structure.

---

## 3. How does knowledge evolve?

A new page is indexed. The cognitive event is **not** “+1 document.” It is **“new observations → possible knowledge change.”**

### 3.1 Observation intake

New sensory input arrives (extracted meaningful content — the system may discard boilerplate at observation time as *non-informative signal*).

The engine asks: **Does this observation contain interpretable communicative intent?**  
(Navigation chrome, cookie banners, repeated footers → low information; may produce no claims.)

### 3.2 Claim extraction

From informative observations, candidate claims are proposed:

- explicit statements
- list memberships (“our products include…”)
- definitions, procedures, constraints
- implicit claims (careful — lower confidence by default)

Each candidate claim is **provisional** until matched against memory.

### 3.3 Memory matching (the core cognitive loop)

For each candidate claim, the engine asks:

| Question | Possible outcome |
|----------|------------------|
| Have I seen this before (same proposition)? | **Strengthen** — add evidence, increase confidence if independent |
| Is this similar but not identical? | **Merge**, **fork**, or **specialize** (see below) |
| Does this contradict something I hold? | **Conflict detection** — do not silently overwrite |
| Is this more specific than a general claim? | **Specialize** — refine a broader claim |
| Is this more general than specific claims? | **Generalize** — or keep both with scope tags |
| Is this from a more authoritative context? | **Re-weight** evidence, possibly revise canonical stance |
| Is this duplicate evidence? | **Consolidate** — same claim, no confidence gain from redundancy |
| Is this obsolete? | **Temporal revision** — mark prior claim as superseded |

### 3.4 Merge vs split (concept evolution)

**Merge** when two claim clusters are semantically the same under all relevant scopes — the engine was duplicating understanding.

**Split** when one cluster covers distinct scopes that cause reasoning errors — e.g., “fees” that mean different things in consumer vs business sections.

**Concept regions** split and merge as a **side effect** of claim dynamics — not as a separate manual taxonomy operation.

### 3.5 Forgetting (necessary, not failure)

Forgetting is **not** deletion of observations (audit may require retention).  
Forgetting is **cognitive demotion**:

- obsolete claims move to historical state
- superseded beliefs lose active weight
- low-evidence orphan claims decay unless reinforced

A site that removed a product should yield: *“the site no longer presents evidence for X”* — not *“X is false.”*

### 3.6 Complete evolution cycle (narrative)

```
New observation
  → extract candidate claims
  → for each claim:
       match to memory
       update evidence graph (support / duplicate / conflict)
       adjust confidence (Bayesian or equivalent — not a manual slider)
       update concept region membership
       update ignorance map (did we fill a gap?)
       update authority map (did canonical source change?)
  → periodic consolidation:
       merge redundant claims
       split overloaded clusters
       decay unreinforced low-confidence claims
  → emit learning summary (for ops, not for admin tuning):
       "discovered 3 new product claims"
       "strengthened 'contact information' region"
       "detected conflict in fee structure"
       "no evidence found for 'international transfers'"
```

**Knowledge acquisition is incremental belief revision**, not append-only indexing.

---

## 4. What is a belief?

### Your proposal (evaluated critically)

You suggested the engine should store **beliefs**, not information, with:

- supporting evidence  
- conflicting evidence  
- confidence  
- freshness  
- coverage  
- uncertainty  
- history  

**Verdict: directionally right, architecturally incomplete if beliefs are the only primitive.**

### Why “beliefs only” is risky

1. **Beliefs are conclusions.** If you store only conclusions, you lose **why** — and cannot revise cleanly when new evidence arrives. You need decomposable claims beneath beliefs.

2. **Beliefs compound.** “The site is trustworthy” + “Product X is free” → fragile if X is actually conditional. Compound beliefs hide structure.

3. **Beliefs invite false certainty.** A belief store without explicit conflict types tends to collapse to a single confidence number — hiding “two sources disagree.”

4. **Beliefs are query-dependent aggregations.** “What credit products exist?” activates a different aggregation than “Is Premium Card free?” — the same underlying claims, different belief states. Materializing all belief states is combinatorially explosive.

### A better model: **Layered Epistemic Memory**

| Layer | What it holds | Mutability |
|-------|---------------|------------|
| **Observations** | Raw informative extractions (events) | Immutable log |
| **Claims** | Attributed propositions | Revisable, mergeable, splittable |
| **Belief states** | Consolidated stance on a **claim cluster** for a **scope** | Derived, cacheable, revisable |
| **Concept regions** | Emergent organization over claims | Continuously reshaped |
| **Ignorance records** | Explicit absence / insufficiency | First-class |

A **belief** is then well-defined:

> A **belief** is the engine’s current epistemic stance toward a scoped cluster of related claims — including support structure, conflict structure, confidence distribution, and temporal validity.

Your list maps cleanly onto **belief states**, not raw storage:

| Your field | Belongs on |
|------------|------------|
| supporting evidence | Claim + Belief state |
| conflicting evidence | Belief state (must be explicit, not folded into confidence) |
| confidence | Belief state (prefer distribution, not scalar) |
| freshness | Claim + evidence timestamps |
| coverage | Region-level ignorance map |
| uncertainty | Typed epistemic status |
| history | Revision chain on claims and belief states |

### Recommendation

**Store claims. Derive beliefs. Cache belief states where reasoning cost demands it.**

Do not store “information.” Do not store “beliefs” without claim decomposition.  
The engine’s honesty lives in the **claim layer**; its efficiency lives in the **belief cache**.

---

## 5. How should uncertainty be represented?

Humans reason under uncertainty with **types**, not just percentages. The engine should too.

### 5.1 Typed epistemic status (not one confidence number)

| Status | Meaning | User-facing behavior |
|--------|---------|----------------------|
| **Established** | Multiple independent sources, no material conflict | Answer directly |
| **Supported** | Adequate evidence, minor gaps | Answer with light hedging |
| **Weak** | Single source or inferential only | Answer with explicit caution |
| **Conflicting** | Credible contradictory evidence | Present conflict, do not pick silently |
| **Absent** | No claims in region | “Site does not contain this information” |
| **Unbounded** | Partial enumeration | “Site mentions X, Y, Z — completeness unknown” |
| **Superseded** | Previously held, now demoted | “Earlier content suggested X; current evidence suggests Y” |
| **Out of scope** | Question requires world knowledge, not site knowledge | Refuse gracefully |

### 5.2 Confidence as distribution, not scalar

“I am 95% confident” is often **false precision**.

Better internal representation:

- **Evidence count** (independent vs duplicate)
- **Source diversity** (one page vs cross-section agreement)
- **Conflict penalty** (automatic when contradictions exist)
- **Extraction confidence** (how sure are we we parsed the claim correctly?)
- **Completeness estimate** (for enumeration questions — especially important)

A scalar confidence can be a **projection for UI** — not the cognitive primitive.

### 5.3 Explicit ignorance is knowledge

“I don’t know” must be **first-class**, not failure:

- **Ignorance of absence:** no evidence exists  
- **Ignorance of completeness:** some evidence, enumeration may be incomplete  
- **Ignorance of resolution:** evidence conflicts, cannot adjudicate  
- **Ignorance of interpretation:** observation too ambiguous to claim  

### 5.4 Revision memory

“I used to believe X but new evidence suggests Y” requires:

- **claim lineage** (X → Y supersession link)
- **temporal scope** (when each was active)
- **reason for revision** (new observation, conflict resolution, source demotion)

This is not nostalgia — it is **intellectual honesty** and **debuggability**.

---

## 6. How should reasoning work?

**Scenario:** User asks *“What credit products exist?”*

Assume perfect memory. No retrieval. No software modules. Pure cognitive process.

### Step 1 — Interpret the information need

Not keyword match. The engine parses:

- **Question type:** enumeration (open set)
- **Domain anchor:** “credit products” (emergent region — not “product_page”)
- **Completeness expectation:** user likely wants site’s offering, not global financial taxonomy
- **Risk:** enumeration questions imply false completeness if answered without hedging

### Step 2 — Activate relevant memory regions

Concept regions overlapping “credit” + “product/service offering” activate.  
This is **spread activation** in claim-space — not vector search as primary logic (similarity may *trigger* activation, but reasoning is structural).

### Step 3 — Collect candidate claims

Gather all claims of types:

- product/service existence
- list membership
- category inclusion

Exclude:

- navigational mentions without substantive claims
- third-party references
- historical products marked superseded (unless question is temporal)

### Step 4 — Assess evidence structure

For each candidate:

- How many **independent** supporting observations?
- Are list pages corroborated by detail pages?
- Are there duplicates (same text, mirrored pages)?
- Any conflicts (product listed but discontinued elsewhere)?

### Step 5 — Evaluate completeness (critical for enumeration)

The engine must ask:

> “Does the site present itself as offering a **closed list** or an **open catalog**?”

If open catalog → answer must **not** imply exhaustiveness.  
This is a **meta-claim** about the site’s own communicative structure — inferable from how lists are presented.

### Step 6 — Resolve belief state

Form aggregated belief:

- **Products confidently established:** A, B, C (multi-source)
- **Products weakly mentioned:** D (single mention in nav)
- **Conflicts:** E (listed vs removed)
- **Ignorance:** unknown whether F exists — no evidence

### Step 7 — Decide answer posture

Not “generate text.” Choose **speech act**:

- Enumerate with completeness disclaimer
- Refuse if zero evidence
- Ask clarifying question if region ambiguous (credit vs debit vs all cards)

### Step 8 — Self-evaluate before speaking

- Am I implying completeness I cannot justify?
- Am I hiding conflict?
- Am I answering from one weak page?
- Should I say “site does not provide enough information”?

### Step 9 — Construct response from belief state

Language generation is **last** — packaging of a resolved epistemic object.

**Notice:** nowhere did the engine “search.” It **activated memory, evaluated evidence structure, and chose an honest speech act.** Retrieval, in a software system, exists only to **populate or refresh** memory — not to *be* the thinking.

---

## 7. Hierarchy of concepts

From bottom (contact with world) to top ( outward behavior):

```
┌─────────────────────────────────────────────────────────┐
│  ANSWER / SPEECH ACT                                     │  ← outward behavior
│  (response chosen under epistemic constraints)           │
├─────────────────────────────────────────────────────────┤
│  REASONING                                               │  ← process: need → memory → stance
│  (active manipulation of memory to resolve a question)   │
├─────────────────────────────────────────────────────────┤
│  UNDERSTANDING                                           │  ← situational comprehension
│  (grasp of what a question requires from THIS site)      │
├─────────────────────────────────────────────────────────┤
│  BELIEF STATE                                            │  ← consolidated epistemic stance
│  (confidence, conflict, coverage for a scoped cluster)   │
├─────────────────────────────────────────────────────────┤
│  CONCEPT REGION                                          │  ← emergent organization
│  (discovered cluster in claim-space — not predefined)    │
├─────────────────────────────────────────────────────────┤
│  CLAIM                                                   │  ← atomic knowledge unit
│  (attributed proposition)                                │
├─────────────────────────────────────────────────────────┤
│  EVIDENCE                                                │  ← justification link
│  (observation → claim, with role: support/infer/conflict)│
├─────────────────────────────────────────────────────────┤
│  OBSERVATION                                             │  ← informative extraction event
│  (meaningful content from a page/file at a time)         │
├─────────────────────────────────────────────────────────┤
│  DOCUMENT / PAGE / CHUNK                                 │  ← world artifacts (non-cognitive)
│  (storage and sensing only — not knowledge)              │
└─────────────────────────────────────────────────────────┘
```

### Relationships (precise)

| Term | Definition |
|------|------------|
| **Document/Page** | Source artifact in the world. Cognitive system should forget these after extracting observations. |
| **Chunk** | Mechanical subdivision for sensing/indexing. Not a cognitive entity. |
| **Observation** | “We read something informative at time T from source S.” |
| **Evidence** | “Observation O supports/contradicts claim C in role R.” |
| **Claim** | “The site asserts proposition P (with scope).” |
| **Concept region** | Emergent neighborhood of related claims — a nameable topic, not predefined. |
| **Belief state** | Engine’s current stance on a scoped claim cluster. |
| **Understanding** | Mapping a user need to regions, claim types, and completeness requirements. |
| **Reasoning** | Process that produces a belief state sufficient for action. |
| **Knowledge** | The **whole memory** — claims, regions, ignorance, revision history — not any single layer. |
| **Confidence** | Projection of epistemic status — not a separate layer. |

**Knowledge** is the entire epistemic memory.  
**Understanding** is need-relative activation of that memory.  
**Reasoning** is transformation of memory into a justified stance.  
**Documents** are how the world is sensed — nothing more.

---

## 7b. Challenge to your terminology

You listed **Concepts** alongside **Knowledge** and **Understanding** as if they are peers. They are not.

- **Concepts** are **compression** — useful for human and machine efficiency, dangerous if reified as ontology.
- Treating concepts as primary leads back to **page categories by another name**.

**Concept regions should be emergent views over claims**, revisable when claims merge/split — not stored as fixed nodes that claims attach to.

---

## 8. Is a Knowledge Graph really necessary?

### Short answer

**No — not as the cognitive core.**  
A graph is one **projection** of epistemic memory, useful for certain queries, insufficient for others.

### The mistake to avoid

Building a graph because “knowledge = nodes + edges” confuses **visualization** with ** cognition**. Graphs excel at explicit relationships. Websites communicate mostly through **implicit, textual, overlapping assertions** — graph edges are often **post-hoc guesses**.

### Comparison of internal representations

| Representation | Strengths | Weaknesses | Role in Knowledge OS |
|----------------|-----------|------------|---------------------|
| **Claim store (logical/epistemic)** | Honest about uncertainty, conflict, revision; closest to cognition | Needs consolidation; similarity matching hard | **Primary memory** |
| **Vector semantic space** | Discovery, fuzzy match, merge candidates | No structure; no conflict; false neighbors | **Perception index** (sense, not memory) |
| **Graph (entities + relations)** | Multi-hop traversal, explicit links | Brittle; ontology drift; edge explosion | **Optional projection** |
| **Concept regions (clusters)** | Overview, coverage maps, breadth questions | Loses nuance if over-compressed | **Organizational view** |
| **Belief cache** | Fast query-time stance | Stale if not invalidated on revision | **Derived performance layer** |
| **Ignorance map** | Trust, completeness | Must be maintained actively | **First-class memory** |
| **Temporal revision log** | Supersession, audit | Storage cost | **History layer** |

### Recommended cognitive architecture (representation-agnostic)

```
         ┌──────────────────────────────────────┐
         │     EPISTEMIC MEMORY (core)         │
         │  claims + evidence + ignorance +    │
         │  revision + belief states           │
         └──────────────┬───────────────────────┘
                        │ projections (on demand)
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   Similarity      Graph view      Region map
   index           (optional)      (emergent)
   (sense)                         (overview)
```

**The graph is a lens, not the mind.**

When graph traversal helps (multi-hop: “which products share property P mentioned on unrelated pages?”), generate the graph **from claims** for that query. Do not maintain a monolithic graph as source of truth.

### Could something beat all of these?

Long-term, a **generative world model** — internal simulation of “what this organization is and offers” — may outperform static structures. That is Phase 5+ research. Near-term, **claim-centric epistemic memory** is the honest foundation.

---

## 9. Long-term evolution (5-year horizon)

After millions of sites, what changed is not “bigger graph.” It is **richer epistemics**.

### 9.1 Memory shape

- **Cross-site abstraction without shared ontology:** “financial product enumeration pages” as a **pattern of claim structures**, not a category label
- **Meta-learning:** which evidence patterns predict answer quality (lists + detail pages > nav mentions)
- **Federated ignorance:** knowing what classes of sites typically omit (pricing, SLAs) without hardcoding industries
- **Provenance chains:** answer traceable through claim → evidence → observation — for trust and compliance

### 9.2 What gets smarter

| Dimension | Today (typical RAG) | Mature Knowledge OS |
|-----------|---------------------|---------------------|
| Indexing | Store text | Revise beliefs |
| New site | Configure presets | Zero-config claim bootstrap |
| Conflict | Hidden or averaged | Explicit conflict speech acts |
| Enumeration | Over-confident lists | Completeness-aware answers |
| Obsolescence | Stale chunks | Supersession tracking |
| Cross-site | Siloed indexes | Shared epistemic patterns (not shared facts) |

### 9.3 What must NOT change

The **cognitive invariants** (Section 10) — even if every storage technology is replaced.

### 9.4 Risks at scale

- **Claim explosion** without aggressive consolidation  
- **False merge** (collapsing distinct propositions)  
- **False split** (fragmenting one proposition)  
- **Belief cache staleness**  
- **Cross-site leakage** (treating patterns as facts)

Scale demands **better epistemics**, not bigger indexes.

---

## 10. Immutable architectural principles

These must survive every refactor — including database, model, and interface changes.

### Epistemic principles

1. **Claims before beliefs.** Beliefs are derived; claims are grounded.  
2. **Evidence before answers.** No speech act without evidential audit.  
3. **Ignorance is knowledge.** Absence, conflict, and incompleteness are first-class.  
4. **The site asserts; the engine does not adjudicate truth.** Ground answers in communicative content, not world truth.  
5. **Confidence is structured, not cosmetic.** Typed status beats false precision.  
6. **Revision over overwrite.** Supersede; do not silently delete cognitive history.

### Cognitive principles

7. **Understanding before action.** Resolve the information need before gathering evidence.  
8. **Reasoning before language.** Answers are packaging of epistemic states, not search results summarized.  
9. **Enumeration is dangerous.** List questions require completeness reasoning by default.  
10. **Conflict must be spoken.** Never average contradictions into silent confidence.  
11. **Concepts emerge; they are not installed.** No ontology as foundation.  
12. **Observations are sacred; interpretations are revisable.** Keep the audit trail separate from belief.

### Autonomy principles

13. **Discovery over configuration.** If a human must tune it, the capability is missing.  
14. **Industries do not exist inside the engine.** Only patterns of claims.  
15. **Every index event is a learning event.** Measure learning, not chunk count.  
16. **Self-critique before output.** Ask whether the answer is justified, not whether it is fluent.

### Anti-principles (never violate)

17. **Never treat similarity as understanding.**  
18. **Never treat storage as knowledge.**  
19. **Never treat retrieval as reasoning.**  
20. **Never hide uncertainty to please the user.**  
21. **Never hardcode what can be inferred.**  
22. **Never optimize infrastructure at the expense of epistemic honesty.**

### Better than your examples

Your examples were good starting points. Stronger formulations:

| Weaker | Stronger |
|--------|----------|
| Knowledge before documents | **Claims before containers** |
| Understanding before retrieval | **Reasoning before search** |
| Evidence before answers | **Evidential audit before speech acts** |

---

## Critical evaluation of your direction

### What you got right

- **Rejecting documents, retrieval, and graphs as goals** — essential category correction.  
- **Belief-oriented memory** — correct instinct that the engine needs epistemic stance, not file metadata.  
- **Uncertainty as first-class** — mandatory for trust.  
- **Autonomous discovery** — the only scalable path.

### Where I push back

1. **Beliefs alone are insufficient.** Without a claim layer, revision and explainability collapse. Store claims; derive beliefs.

2. **Concepts as mental furniture are dangerous.** They reintroduce ontology through the back door. Use **regions** as emergent compression, always revisable.

3. **“Knowledge Graph” as mental model is seductive and wrong.** Graphs are projections. The mind is claim-epistemic, not node-edge.

4. **Source Intelligence as a subsystem name encodes the wrong frame.** It suggests “smart documents.” The right frame is **Claim Extraction and Belief Revision** — sensing and learning, not “source profiling.”

5. **Confidence scores are often harmful.** Typed epistemic status + evidence structure beats a single number.

6. **Completeness reasoning is non-optional.** Most real-world failures on websites are not wrong facts — they are **over-complete lists** and **silent conflict**.

---

## What this implies for the platform (without implementing it)

The next generation platform is not:

- a better retriever  
- a better graph builder  
- a better Source Intelligence schema  

It is an **Epistemic Memory Engine** that:

1. **Extracts claims** from observations  
2. **Revises belief states** as evidence accumulates  
3. **Maps ignorance** explicitly  
4. **Reasons** about user needs against that memory  
5. **Speaks** only after self-evaluation  

Everything else — vectors, graphs, SQL, APIs — is **machinery**.

---

## Suggested name for the cognitive core

Not “Knowledge Graph.” Not “Source Intelligence.” Not “Retrieval Engine.”

**Epistemic Memory** — the system’s living, uncertain, revisable model of what the world (website) communicates.

Understanding activates it.  
Reasoning traverses it.  
Answers express belief states derived from it.

---

## Related documents

| Document | Relationship |
|----------|--------------|
| `KNOWLEDGE_INTELLIGENCE_ENGINE.md` | Vision — this document grounds it cognitively |
| `RFC-0001-KNOWLEDGE-OS-CORE.md` | Product identity — must align with epistemic model |
| `ARCHITECTURE_REVIEW_KNOWLEDGE_OS.md` | Software gap analysis — secondary to this document |
| `KNOWLEDGE_OS_ARCHITECTURE_v1.md` | Engineering contract — subsystems, events, MVP phases |
| `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` | Zero-downtime migration execution plan |
| `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md` | Active acquisition — how memory maintains itself |
| `SEMANTIC_UNDERSTANDING_MVP.md` | Near-term software path — should be reframed as partial Epistemic Memory |

**This document supersedes software-first framing when the two conflict.**
