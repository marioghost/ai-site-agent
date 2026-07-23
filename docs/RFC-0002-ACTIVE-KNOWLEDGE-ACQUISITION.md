# RFC-0002: Active Knowledge Acquisition

**Subtitle:** Designing the Curiosity Engine (and what “curiosity” actually is)  
**Status:** Proposed  
**Extends:** `COGNITIVE_ARCHITECTURE.md` (Epistemic Memory)  
**Constraint:** Cognitive architecture only — no implementation, APIs, schemas, or code

---

## Preamble: From passive memory to active mind

RFC-0001 and the Epistemic Memory model describe a system that **knows** and **reasons**.

That model is still **fundamentally reactive**:

```
World delivers observation → engine updates memory → user asks question → engine answers
```

Humans do not stop learning when the book is closed. They notice:

- “That list felt incomplete.”
- “These two chapters contradict.”
- “They mention X everywhere but never explain it.”
- “There should be a page about pricing — where is it?”

That is not retrieval. That is **epistemic discontent** — a felt imbalance in one’s model of what is known.

Your proposal to add **Active Knowledge Acquisition** is correct and necessary.

Your label **Curiosity Engine** is evocative but **partially misleading**. This document defines what curiosity *must mean* inside the engine — and argues for a sharper cognitive primitive beneath it: **Epistemic Tension**.

---

## Executive thesis

> **The engine should not wait to be fed. It should maintain itself by resolving structured ignorance.**

“Curiosity” is the **motivational surface** of a deeper process:

**Epistemic Maintenance** — continuous detection, prioritization, and reduction of *epistemic tension* in memory.

Curiosity without tension is **random exploration** (hallucinated learning goals).  
Tension without prioritization is **paralysis** (500 unanswered questions).  
Maintenance without closure criteria is **infinite crawl** (never “smart enough”).

The Curiosity Engine is therefore **not a search module**. It is the **homeostatic regulator** of Epistemic Memory.

---

## Challenge to RFC-0001 (respectful revision)

RFC-0001 states: *“Every component must learn”* and *“The system becomes more intelligent after every indexing run.”*

**Partially wrong as stated.**

Not every observation warrants active investigation. Not every gap is fillable from the site. Not every weak belief deserves escalation.

**Revision:**

- **Passive learning** (observation → claim revision) is the default and cheap path.
- **Active acquisition** is triggered only when **epistemic tension** exceeds a **salience threshold** relative to **resolution cost** and **expected epistemic leverage**.
- “Smarter” means **better-structured, more honest memory** — not more pages indexed, not more questions asked.

RFC-0001’s autonomy principle survives. The mechanism becomes **selective**, not omnivorous.

---

## 1. What is Curiosity?

### 1.1 The wrong answer

Curiosity is **not**:

- wanting more data
- feeling uncertain (uncertainty is everywhere — most of it is benign)
- asking random questions
- crawling more links because links exist
- maximizing graph completeness

That is a **data-hungry crawler with an LLM**, not intelligence.

### 1.2 The right answer

Inside this engine, **curiosity is the allocation of attention to epistemic tension**.

Formally:

> **Curiosity** = the policy that selects which **epistemic tensions** to act upon, given limited investigation budget.

Curiosity is **not a thing stored in memory**. It is a **process** — attention routing over gaps, conflicts, and structural anomalies.

### 1.3 What epistemic tension is

**Epistemic tension** is a detected imbalance in memory that **blocks or degrades** reliable reasoning.

|Tension type| Cognitive meaning |
|-------------|-------------------|
| **Support deficit** | Important claim lacks independent evidence |
| **Completeness bound** | Enumeration likely open but presented as closed |
| **Conflict** | Credible claims cannot cohere |
| **Referential void** | Claim or structure references uninstantiated content |
| **Authority vacuum** | Region lacks canonical explainer despite centrality |
| **Isolation** | Concept region referenced often but never substantiated |
| **Staleness** | Temporal signals suggest supersession not yet integrated |
| **Procedure gap** | Multi-step claim missing prerequisite steps |
| **Boundary ignorance** | Scope of a claim unclear (who/what/when) |

Curiosity is **multi-signal**. No single trigger suffices.

### 1.3b Mapping your candidates

| Your candidate | Verdict |
|----------------|---------|
| Missing evidence | Yes — **support deficit** |
| High uncertainty | **Only if salient** — weak nav mention ≠ tension |
| Contradictions | Yes — **conflict** |
| Weak beliefs | **Only if belief is load-bearing** for a region |
| Missing relationships | Yes — **isolation / referential void** |
| Missing observations | Yes — but distinguish **absent from site** vs **not yet crawled** |

**Missing from your list (critical):**

- **Completeness misrepresentation** — the engine might *answer* confidently from an incomplete list unless tension exists around enumeration bounds
- **Blocking tension** — gap prevents answering a *class* of user questions (higher priority than cosmetic gaps)
- **Resolution futility** — tension that **cannot** be resolved from this site should be **closed**, not pursued forever

---

## 2. What should trigger curiosity?

Your examples are **necessary but not sufficient**. Below is a fuller trigger taxonomy.

### 2.1 Evidence-structure triggers

- Single-source support for a **central** claim cluster
- All sources are **duplicates** (mirrors, boilerplate) — false confidence
- Evidence is **inferential only** (implied, not stated) for a high-stakes claim
- Claim supported only by **navigational mention** without substantive body

### 2.2 Structural triggers (site-as-hypertext, not as graph DB)

- Link or reference to content not yet observed (**referential void**)
- List pattern with cardinality hints (“see all 12 products”) vs observed count ≠ 12
- Hub page references detail pages that don’t exist in memory
- Procedure references step N+1 never observed
- Sitemap/frontier suggests URL class never interpreted into claims

### 2.3 Semantic triggers

- Two claims same scope, incompatible predicates (**conflict**)
- Claim cluster with high **betweenness** (many regions point to it) but low claim density (**isolation**)
- Region expected to have definitional claim (site communicates as reference) but only has peripheral mentions

### 2.4 Reasoning-failure triggers (strongest signal)

When **Reasoning** attempts to answer and produces:

- **Refusal** due to absence — tension confirmed
- **Conflict speech act** — tension escalated
- **Unbounded enumeration** — completeness tension surfaced
- **Low self-evaluation score** — meta-tension: “I shouldn’t speak yet”

**Critical insight:** User queries are valuable not as training data but as **stress tests** that reveal load-bearing tensions. This is not “analytics-driven tuning” — it is **epistemic feedback** without hardcoded intent categories.

### 2.5 Temporal triggers

- Observation timestamps diverge sharply for same claim cluster
- Claim marked active but only old evidence supports it
- Site communicates “updated” signals (dates, version language) inconsistent with memory

### 2.6 What should NOT trigger curiosity

| Non-trigger | Why |
|-------------|-----|
| Low confidence on **peripheral** claim | Noise — not worth budget |
| “Could there be more pages in the universe?” | Unbounded speculation |
| Missing world knowledge (global product catalog) | **Out of site scope** — close gap as unresolvable |
| Every weak belief everywhere | Paralysis — prioritize by salience |
| Similarity neighbors in embedding space | Similarity ≠ epistemic need |

---

## 3. Knowledge Gaps

### 3.1 “No evidence” is too coarse

The engine needs a **typed gap ontology** — first-class cognitive objects, not boolean absence.

### 3.2 Gap types

| Gap type | Meaning | Typical resolution |
|----------|---------|------------------|
| **Unknown** | No claim exists; no hook observed | May remain forever — close if no hook |
| **Unobserved** | Hook exists (link, reference) but no observation | Active acquisition candidate |
| **Incomplete** | Partial enumeration; bound unknown | Seek corroborating list/detail structure |
| **Under-supported** | Claim exists; independence insufficient | Seek additional evidence class |
| **Conflicting** | Mutually incompatible claims | Seek adjudication evidence or escalate conflict |
| **Unverified** | Plausible but extraction confidence low | Re-read observation or seek confirmation |
| **Unscoped** | Claim truth unclear (audience, time, product variant) | Seek qualifying context |
| **Stale** | Supersession suspected | Seek newer observation |
| **Unresolvable (site-bound)** | Site cannot contain answer by nature | **Close** — not a learning failure |

### 3.3 Gap as cognitive object

Each gap should carry (conceptually, not as schema):

- **Anchor** — claim(s) or region it attaches to
- **Type** — from taxonomy above
- **Severity** — impact on reasoning reliability
- **Blocking** — does it block a class of answers?
- **Hooks** — what observed structure motivated the gap (link, list pattern, reference)
- **Resolution criteria** — what observation would **close** or **escalate** the gap
- **Futility estimate** — probability gap is site-unresolvable
- **Status** — open | investigating | resolved | closed-unresolvable

**Ignorance is not failure. Unclosed infinite gaps are failure.**

---

## 4. Question Generation

### 4.1 Questions are not the primitive

**Challenge:** Self-generated questions like “Are there more products?” are **natural language projections** of gaps.

The primitive is the **Investigation Hypothesis**:

> “If I obtain observation O in region R, tension T will decrease by amount Δ.”

Questions are **human-readable labels** for investigation hypotheses — useful for explainability, not for cognition.

### 4.2 How hypotheses are generated

From gap type + hooks:

| Gap | Investigation hypothesis (internal) |
|-----|-------------------------------------|
| Unobserved referent | “Following reference hook H yields substantive observation” |
| Incomplete enumeration | “Detail pages or secondary list exist for items in set S” |
| Conflict | “Authoritative observation resolves predicate P” |
| Isolation | “Definitional claim exists for central referent R” |
| Stale | “Newer observation supersedes claim C” |

Generation is **gap-driven**, not LLM-brainstorm-driven. LLM may **phrase** hypotheses; it should not **invent** them without anchors.

### 4.3 Prioritization (preview — full model in §6)

Hypotheses rank by:

1. **Epistemic leverage** — expected reduction in blocking tension  
2. **Salience** — centrality of anchored region in memory  
3. **Hook strength** — concrete referential evidence vs vague hunch  
4. **Resolution cost** — expected effort to obtain observation  
5. **Reasoning stress** — recent failures implicating this gap  

Low hook strength + low leverage = **suppress** (hallucination guard).

---

## 5. Learning Goals

### 5.1 Should an active list exist?

**Yes — but not as “learning objectives” in the human study sense.**

Call it the **Epistemic Agenda**:

> A dynamic, prioritized queue of **open tensions** and their **active investigation hypotheses** — not a todo list of topics.

### 5.2 Bad learning goals (avoid)

- “Improve understanding of mortgage products” — too vague, industry-flavored, unmeasurable
- “Understand the site better” — meaningless
- “Index more pages” — metric chasing

### 5.3 Good agenda items (examples)

- **T-042:** Conflict between fee claims F₁ and F₂ on product P — *blocking pricing answers* — hypothesis: locate terms page  
- **T-108:** Product P listed in hub, zero detail claims — *incomplete product region* — hypothesis: follow /products/p/ link  
- **T-201:** Referent “deposit insurance” appears 14×, definitional claim absent — *isolation* — hypothesis: seek FAQ or legal cluster  

Each item ties to **tension ID**, not topic name.

### 5.4 How the agenda evolves

```
New tension detected → enqueue with priority
Investigation succeeds → revise claims → recompute tension → resolve or downgrade
Investigation fails → increase futility estimate → retry with backoff or close
New observation (passive) → may resolve multiple agenda items without active work
User reasoning stress → boost priority of implicated tensions (not new random goals)
Time decay → peripheral tensions deprioritize unless re-triggered
```

The agenda **shrinks** as memory matures. A healthy mature site reaches **agenda equilibrium** — mostly staleness and conflict monitoring, not discovery frenzy.

---

## 6. Planning — 500 unanswered questions

### 6.1 Most should never be “answered”

A system that treats every generated question as valid will **crawl forever** and **confuse speculation with learning**.

**Mandatory filtering:**

1. **Anchor filter** — no hook → no active investigation  
2. **Futility filter** — site-bound unresolvable → close  
3. **Salience floor** — peripheral tension → defer indefinitely  
4. **Budget constraint** — only top-k investigations per cycle  

### 6.2 Priority function (conceptual)

Investigation priority ∝  

**(Blocking × Leverage × Stress) / (Cost × Futility)**

Where:

- **Blocking** — prevents reliable speech acts for question class  
- **Leverage** — how many claims/beliefs revise if resolved  
- **Stress** — recent reasoning failures touching this tension  
- **Cost** — expected acquisition effort (depth, ambiguity)  
- **Futility** — P(gap is unresolvable from site)  

Curiosity **has priorities**. It must. Attention is finite — in humans and in engines.

### 6.3 Investigation actions (cognitive, not software)

What “investigate” **means** cognitively:

| Action | When |
|--------|------|
| **Follow referential hook** | Unobserved gap with link/reference |
| **Re-interpret observation** | Unverified gap, low extraction confidence |
| **Seek corroboration class** | Under-supported central claim |
| **Seek adjudication context** | Conflict gap |
| **Expand enumeration boundary** | Incomplete list with structural hints |
| **Wait** | Passive acquisition may resolve on next scheduled index |
| **Close** | Futility exceeds threshold |

Not every investigation requires new pages. **Re-interpretation** is under-rated — the evidence was already observed; the claim extraction was weak.

---

## 7. The Learning Loop

### 7.1 Challenge to the proposed loop

Your sketch:

```
Observe → Understand → Detect uncertainty → Generate questions →
Plan → Acquire evidence → Revise beliefs → Repeat
```

**Problems:**

1. **Linear** — real maintenance is concurrent and overlapping  
2. **“Understand” is vague** — should be **consolidate memory**  
3. **“Acquire evidence”** implies external action always — sometimes re-interpretation suffices  
4. **No closure** — infinite loop anxiety  
5. **Passive and active paths merged** — they should be distinct but coupled  

### 7.2 Better loop: Epistemic Maintenance Cycle

Two coupled rhythms:

#### Rhythm A — Passive integration (every observation)

```
Observation arrives
  → extract candidate claims
  → integrate into memory (match, merge, conflict, supersede)
  → update belief states
  → surface NEW or CHANGED tensions
  → enqueue agenda items
```

#### Rhythm B — Active maintenance (continuous, budgeted)

```
Scan tension field (not “all questions”)
  → rank open tensions by priority function
  → select investigation hypotheses within budget
  → execute investigation actions
  → integrate new/ch re-read observations (→ Rhythm A)
  → evaluate: tension reduced?
       yes → resolve/close agenda item
       no  → increase futility, retry or close
  → consolidate memory (merge/split claims, decay orphans)
  → emit learning report (internal): tensions opened/closed, not pages counted
```

#### Rhythm C — Reasoning stress feedback (event-driven)

```
User question → reasoning → self-evaluation weak
  → identify load-bearing tensions implicated
  → boost agenda priority (not: generate new random questions)
  → optional: defer answer harder if tension is blocking
```

### 7.3 Diagram

```
        ┌─────────────────────────────────────┐
        │         EPIS TEMIC MEMORY            │
        │  claims · beliefs · gaps · tensions  │
        └───────────┬────────────▲────────────┘
                    │            │
         passive    │            │  revise
         integration│            │
                    ▼            │
        ┌───────────────────┐    │
        │   OBSERVATION      │    │
        │   (world / site)   │    │
        └───────────────────┘    │
                    │            │
                    ▼            │
        ┌─────────────────────────────────────┐
        │      TENSION SURFACING               │
        │  (structure + reasoning stress)      │
        └───────────┬─────────────────────────┘
                    ▼
        ┌─────────────────────────────────────┐
        │      EPIS TEMIC AGENDA               │
        │  prioritized investigation hypotheses│
        └───────────┬─────────────────────────┘
                    ▼
        ┌─────────────────────────────────────┐
        │   ACTIVE ACQUISITION (curiosity)     │
        │  investigate · re-interpret · close  │
        └───────────┬─────────────────────────┘
                    │
                    └──────────────────────────┘

        ┌─────────────────────────────────────┐
        │   REASONING (user or internal)       │──stress──▶ Agenda boost
        └─────────────────────────────────────┘
```

**Curiosity sits in the maintenance loop — not in the answer loop.**

---

## 8. Self-Evaluation — how does the engine know it got smarter?

### 8.1 Wrong metrics (explicitly banned)

- Pages indexed  
- Vectors stored  
- Graph node count  
- Questions generated  
- Crawl coverage percentage  

These measure **activity**, not **understanding**.

### 8.2 Right metrics — epistemic health indicators

| Indicator | Meaning |
|-----------|---------|
| **Blocking tension count** | Down → smarter (fewer answer classes blocked) |
| **Independent evidence ratio** | Up for central claims → smarter |
| **Conflict resolution rate** | Conflicts surfaced AND closed honestly |
| **False completeness rate** | Down — fewer enumeration answers without bounds |
| **Agenda equilibrium time** | Time to reach stable low-tension state for site |
| **Reasoning self-evaluation pass rate** | Up on held-out question stress set |
| **Refusal precision** | Refuses when should; answers when should |
| **Re-interpretation yield** | Claims improved without new pages — extraction got better |
| **Closed-unresolvable accuracy** | Gaps closed as site-bound vs later wrongly closed |

### 8.3 The meta-metric

> **Epistemic honesty under test** — the engine speaks when justified and refuses when not, and its internal tension field **predicts** those outcomes.

Smarter ≠ more answers. Smarter = **more calibrated speech acts**.

---

## 9. Curiosity vs Hallucination

### 9.1 The failure mode

Unanchored curiosity produces:

- “Maybe there is a careers page about quantum computing”  
- “Perhaps the site offers 40 more products”  
- “I should learn about the CEO’s favorite color”  

This is **speculative gap hallucination** — the engine inventing epistemic need without evidential hook.

### 9.2 Guards (cognitive, not rule-based)

**1. Anchor requirement**  
Every active investigation hypothesis must cite at least one **hook** from memory: reference, list structure, conflict pair, reasoning failure trace, or centrality metric with observed referential pressure.

**2. Resolution criterion requirement**  
“If observation O*, claim revision R*” — else not a hypothesis, just a musing.

**3. Futility closure**  
After failed investigations, increase P(unresolvable). Close gap — do not eternal retry.

**4. Scope discipline**  
Engine learns **what the site communicates**, not **what could exist in principle**.

**5. Suppress LLM free-association**  
Language models generate plausible questions. **Gaps generate investigations.** LLM phrasing is output, not source.

### 9.3 Interesting gap vs random speculation

| Interesting gap | Random speculation |
|-----------------|-------------------|
| Referential hook exists | No hook |
| Blocks or degrades reasoning | Peripheral |
| Resolution criteria definable | Vague “learn more” |
| Tension decreases measurably if resolved | No measurable belief revision |
| Repeatedly implicated in reasoning stress | Never implicated |

---

## 10. Long-term evolution

### 10.1 What this process becomes

After years of operation across many sites, Active Knowledge Acquisition becomes:

**An epistemic immune system** — continuous hygiene for belief networks:

- Detect infection (conflict, stale claims)  
- Identify deficiency (support deficit)  
- Distinguish self vs foreign (site scope vs world knowledge)  
- Heal (integrate evidence) or tolerate (close unresolvable)  

It is **not** an eternal curious child clicking every link.

### 10.2 Cross-site learning (without shared facts)

The engine must **not** learn “banks have mortgage pages” as fact.

It may learn **epistemic patterns**:

- List hubs without detail pages often create incomplete product regions  
- Legal footers repeat across mirrors — low independence  
- FAQ clusters often resolve isolation tensions for policy terms  
- Conflict often appears between marketing and terms pages  

These are **meta-tensions about tension** — patterns of how sites fail to communicate coherently.

Transferable **inquiry strategies**, not transferable **ontology**.

### 10.3 Maturity curve

| Stage | Behavior |
|-------|----------|
| **Immature site memory** | High discovery tension — many unobserved hooks, agenda grows |
| **Consolidating** | Rapid tension resolution — agenda peaks then falls |
| **Mature** | Low discovery — monitoring staleness/conflict, incremental updates |
| **Drifting** | Site changes → tension spikes → targeted re-acquisition |

A mature engine spends **more** effort on conflict, staleness, and reasoning-stress feedback — **less** on exploratory curiosity.

### 10.4 Relationship to users

Users remain one interface — but the engine also **questions itself** internally.

Optional future: engine surfaces **epistemic status** to admins (“3 unresolved conflicts affect pricing answers”) — not as config, as **health report**.

---

## 11. Is “Curiosity” the wrong abstraction?

### Verdict

**As a stored trait or module name — yes, slightly wrong.**  
**As a policy over epistemic tension — acceptable metaphor.**

Better primary terms:

| Term | Role |
|------|------|
| **Epistemic Tension** | What exists in memory (structured imbalance) |
| **Epistemic Agenda** | What the engine intends to reduce |
| **Active Acquisition** | What the engine does |
| **Curiosity** | Attention policy over the agenda |

If you rename the subsystem, call it **Epistemic Maintenance** with a **Tension Surfacers** and **Investigation Planner** — curiosity is how it **feels** from outside, not what it **is**.

---

## 12. Immutable principles (RFC-0002)

These extend RFC-0001 and Epistemic Memory principles:

1. **Tension before exploration.** No investigation without structured epistemic imbalance.  
2. **Hooks before hypotheses.** No anchor, no active acquisition.  
3. **Closure before crawl.** Unresolvable gaps must be closed, not chased forever.  
4. **Maintenance before growth.** Consolidate and heal before expanding.  
5. **Reasoning stress is signal.** Failed self-evaluation feeds the agenda — not admin tuning.  
6. **Questions are labels, not primitives.** Investigation hypotheses are cognitive; NL questions are optional skin.  
7. **Re-interpretation is learning.** New pages are not the only evidence source.  
8. **Curiosity is budgeted.** Attention is finite; priority is mandatory.  
9. **Smarter means more calibrated, not more data.**  
10. **Speculation is not curiosity.** Unanchored inquiry is a bug.

---

## 13. Revised full cognitive stack

Integrating RFC-0001, Epistemic Memory, and Active Acquisition:

```
                    ┌─────────────────────┐
                    │   USER / WORLD       │
                    └──────────┬──────────┘
                               │
              observations     │     questions
                    ▼          ▼
        ┌──────────────────────────────────┐
        │      EPIS TEMIC MEMORY            │
        │  observations · claims · beliefs  │
        │  gaps · tensions · agenda         │
        └───────▲──────────────▲────────────┘
                │              │
     passive    │              │  stress feedback
     integration│              │
                │              │
        ┌───────┴──────┐  ┌────┴─────────────┐
        │  ACQUISITION  │  │    REASONING      │
        │  (curiosity / │  │  understand need  │
        │  maintenance) │  │  → belief state   │
        └───────┬──────┘  │  → self-evaluate  │
                │         └─────────┬──────────┘
                │                   │
                └─────────┬─────────┘
                          ▼
                    ┌───────────┐
                    │  ANSWER    │
                    └───────────┘
```

**Passive path:** world → memory  
**Active path:** memory → tension → agenda → acquisition → memory  
**Reasoning path:** question → memory → answer (and stress → agenda)

All three meet in **Epistemic Memory** — not in retrieval.

---

## 14. What this RFC does NOT specify

Deliberately omitted (implementation phase):

- Crawl policies, schedulers, queues  
- APIs, tables, workers  
- When to run maintenance cycle (ops)  
- Exact priority function weights  
- LLM prompt structures for claim extraction  

Those are **engineering consequences** of this cognitive model — not the model itself.

---

## 15. Relationship to prior documents

| Document | Relationship |
|----------|--------------|
| `COGNITIVE_ARCHITECTURE.md` | Defines Epistemic Memory — RFC-0002 extends with maintenance |
| `RFC-0001-KNOWLEDGE-OS-CORE.md` | Product identity — refined: learning is selective, not omnivorous |
| `SEMANTIC_UNDERSTANDING_MVP.md` | Software path — should eventually implement tension/agenda subset |
| `ARCHITECTURE_REVIEW_KNOWLEDGE_OS.md` | Gap analysis — secondary to this RFC |

**When documents conflict, cognitive architecture (Epistemic Memory + Active Acquisition) wins.**

---

## 16. Recommended next step (still no code)

Before implementation:

1. **Reconcile** `SEMANTIC_UNDERSTANDING_MVP.md` with **claim + tension** model (not “concept index” as primary)  
2. Define **minimal tension taxonomy** for first software slice (3–4 types, not 20)  
3. Specify **agenda item lifecycle** as state machine (conceptual)  
4. Identify which existing signals (SI profiles, reasoning failures, link structure) can **surface tensions** without new hardcode  

The first implementation should **detect and display tensions** — not autonomously crawl. **Visibility before autonomy.**

---

## Closing

Passive Epistemic Memory answers: *What does the site appear to say?*

Active Knowledge Acquisition answers: *Where is my model broken, incomplete, or dishonest — and what should I do about it?*

That is the difference between a **database of interpretations** and a **mind that maintains itself**.

Curiosity, properly understood, is not whimsy. It is **disciplined attention to epistemic tension** — the engine’s immune response against ignorance, conflict, and false confidence.

That is RFC-0002.
