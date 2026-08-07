# Engineering Principles

**Status:** Constitution — timeless, binding on every engineer  
**Read before:** Your first line of code on this platform  
**Relationship:** Below vision and frozen architecture; above implementation and tools

This document is **not** an RFC. **Not** architecture. **Not** implementation. **Not** documentation.

It defines **how engineers think** on the Knowledge OS.

The architecture phase is complete. These foundations exist and must not be redesigned:

- `ENGINEERING_MANIFEST.md`
- `RFC-0001-KNOWLEDGE-OS-CORE.md`
- `COGNITIVE_ARCHITECTURE.md`
- `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md`
- `KNOWLEDGE_OS_ARCHITECTURE_v1.md`
- `ARCHITECTURE_CONTRACT_1.0.md` — AI Platform merge-gate constitution
- `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`
- `DEVELOPMENT_CHARTER.md`

If implementation exposes a fundamental flaw: **stop**, write an ADR, make the case — then continue. Architecture changes are **rare**. Disciplined execution is **default**.

---

## How to use this document

- Read once when you join. Re-read when pressure says “just ship it.”
- When two options seem equal, choose the one these principles favor.
- When a principle conflicts with a deadline, do not discard it — find the smallest honest compromise and mark the debt visibly.
- Principles outlive languages, storage, models, and frameworks.

---

# Part I — Principles

## 1. Knowledge before documents

**Principle:** Documents are evidence containers. Knowledge is the product.

**Why it exists:** Most systems “know” files. We must know **what the site communicates** — claims, uncertainty, gaps — not which page was indexed when.

**Good:** A feature improves claim accuracy or surfaces ignorance. Ingest reports “12 claims strengthened,” not “12 pages crawled.”

**Bad:** A feature adds page-type boosts or ranking that treats URLs as the unit of truth.

---

## 2. Evidence before answers

**Principle:** Every answer must be explainable through evidence.

**Why it exists:** Fluent language without grounding is indistinguishable from fabrication. Trust is earned through provenance, not tone.

**Good:** Before speaking, the system can answer: *which observations support this, how independent are they, what was rejected?*

**Bad:** An answer ships because search returned passages and the model sounded confident.

---

## 3. Reasoning before retrieval

**Principle:** Retrieval exists to support reasoning — never the opposite.

**Why it exists:** Search-first systems optimize finding text. We optimize **resolving an information need**, then gather evidence as a tool.

**Good:** The pipeline asks *what knowledge is required* before asking *which passages are nearest*.

**Bad:** User question → similarity search → prompt stuffing → hope.

---

## 4. Inference before configuration

**Principle:** Prefer inference. Avoid configuration.

**Why it exists:** Configuration scales with customers; inference scales with intelligence. Every knob is an admission the engine could not discover something.

**Good:** Concept regions emerge from claims. Completeness is inferred from list structure.

**Bad:** Admin selects an industry preset, sets document priorities, tunes boost sliders for one site.

---

## 5. Learning before hardcoding

**Principle:** If intelligence can replace a rule, replace the rule.

**Why it exists:** Hardcoded rules make one site work and the next fail. Learning makes the **next** site easier, not harder.

**Good:** A new vertical works with zero template because claim extraction and tension surfacing improve.

**Bad:** Each new customer adds another industry-specific branch in core logic.

---

## 6. Understanding before similarity

**Principle:** Similarity is perception. It is not understanding.

**Why it exists:** Similar text can mean different things; different text can express the same claim. Nearest-neighbor search is a **sense organ**, not **thought**.

**Good:** Similarity triggers candidate claims; structure, conflict, and evidence decide belief.

**Bad:** “Top five passages” is treated as “what the system understands.”

---

## 7. Truthfulness before confidence

**Principle:** Never sound certain when evidence is weak.

**Why it exists:** False certainty destroys trust faster than ignorance. Users forgive “I don’t know”; they don’t forgive wrong certainty.

**Good:** Enumeration answers include completeness bounds. Conflicts are spoken, not averaged.

**Bad:** A single navigation mention becomes a confident product list. Contradictory pages produce a smooth summary.

---

## 8. Simplicity before cleverness

**Principle:** Complexity compounds forever. Choose simplicity whenever possible.

**Why it exists:** Clever systems accumulate hidden state. Simple systems accumulate clarity.

**Good:** A new capability fits an existing subsystem boundary without new global concepts.

**Bad:** Each feature adds a parallel pipeline “because it was faster this sprint.”

---

## 9. Architecture before implementation

**Principle:** Never solve architecture problems with implementation hacks.

**Why it exists:** Hacks teach the codebase that structure doesn’t matter. Eventually nobody knows where truth lives.

**Good:** Missing capability → ADR → bounded change → implementation.

**Bad:** Another manual boost because listing pages beat product pages on one customer site.

---

## 10. Replaceability

**Principle:** Every subsystem should be replaceable without rewriting the platform.

**Why it exists:** Tools change. Models change. Storage changes. **Epistemic contracts** should not.

**Good:** Evidence assembly can be replaced; Reasoning and Memory interfaces stay stable.

**Bad:** Business logic scattered so the search layer cannot be swapped without rewriting the answer path.

---

## 11. One responsibility

**Principle:** Each subsystem owns one cognitive job — fully, clearly.

**Why it exists:** God objects hide bugs, block testing, and make migration impossible.

**Good:** Language renders; Reasoning decides; Memory remembers; Executive coordinates.

**Bad:** A single orchestration layer caches, retrieves, prompts, scores, and apologizes.

---

## 12. Boundaries are contracts

**Principle:** Crossing a boundary is an event, not a hidden side effect.

**Why it exists:** Hidden coupling is the silent killer of replaceability and testability.

**Good:** Memory mutates only through integration; Reasoning emits stress signals, not silent writes.

**Bad:** A scorer persists state “for convenience” outside its subsystem.

---

## 13. Memory is authoritative

**Principle:** There is one epistemic source of truth per site.

**Why it exists:** Split brains produce split answers. Operators cannot trust diagnostics if state is duplicated inconsistently.

**Good:** Belief states derive from claims; caches key on memory version.

**Bad:** Inline config, boost tables, and index state each tell a different story.

---

## 14. Observations are sacred; claims are revisable

**Principle:** Keep the audit trail; revise interpretation openly.

**Why it exists:** You cannot debug intelligence without knowing what was read. You cannot trust intelligence without revision and supersession.

**Good:** A page update creates a new observation; claims supersede with lineage.

**Bad:** Overwriting extracted text and pretending history never happened.

---

## 15. Tension is signal, not noise

**Principle:** Gaps, conflicts, and weak support drive learning — not embarrassment.

**Why it exists:** A system that hides tension looks healthy while being dishonest. Maintenance targets **epistemic imbalance**, not page count.

**Good:** Open tensions appear in ops dashboards; agenda items close or resolve with reason.

**Bad:** Low retrieval score is “fixed” with a boost instead of investigating missing claims.

---

## 16. Maintenance is part of intelligence

**Principle:** A mind that never revisits its beliefs is a static index.

**Why it exists:** Sites change. Passive ingest alone is insufficient for long-lived accuracy.

**Good:** Budgeted investigations resolve anchored tensions; futile gaps close.

**Bad:** Infinite crawl without priority; or no self-correction ever.

---

## 17. Explainability is a feature

**Principle:** Explain **decisions**, not internal scores.

**Why it exists:** Operators and users need to trust **why** — not read opaque ranking arithmetic.

**Good:** “Not used: navigation-only mention.” “Conflict: fee stated two ways.”

**Bad:** A numeric score with no semantic story.

---

## 18. Production discipline

**Principle:** Every change must be deployable, observable, rollbackable, and testable.

**Why it exists:** Intelligence means nothing if the platform is down or cannot revert.

**Good:** Feature flags, golden queries, parity before default-on, runbooks.

**Bad:** “We’ll roll forward only” on the reasoning path.

---

## 19. Backward compatibility is respect

**Principle:** Evolution must not casually break operators or integrations.

**Why it exists:** Trust accumulates slowly and burns instantly.

**Good:** Deprecation notices, dual-read paths, legacy behind flag until parity proven.

**Bad:** Removing operator APIs the day before a release without migration path.

---

## 20. Tests protect the mind

**Principle:** Test behaviors that matter: evidence, refusal, parity — not incidental details.

**Why it exists:** Tests encode what we refuse to regress. Wrong tests encode wrong architecture.

**Good:** Golden queries, guard tests that manual boosts stay dead, self-eval triggers refusal.

**Bad:** Tests that lock document-type ordering as if it were law.

---

## 21. Performance serves honesty

**Principle:** Fast wrong answers are failures. Honest reasoning at acceptable latency is success.

**Why it exists:** Optimizing throughput while degrading epistemic quality optimizes the wrong thing.

**Good:** Memory-first routing reduces junk context **and** cost.

**Bad:** Skip self-evaluation “for speed.”

---

## 22. Observability is operational empathy

**Principle:** Measure what operators need to sleep: reasoning latency, tensions, refusals, memory churn — not vanity graphs.

**Why it exists:** You cannot run what you cannot see. Migration without metrics is flight without instruments.

**Good:** Dashboards distinguish legacy vs new path, open conflicts, investigation failures.

**Bad:** Only request volume while answer quality drifts silently.

---

## 23. Refactor toward boundaries

**Principle:** Refactor when responsibilities drift — not when a module “feels long.”

**Why it exists:** Size is a heuristic; boundary violation is a fact.

**Good:** After a release, extract Reasoning because orchestration gained belief logic.

**Bad:** Rename folders for aesthetics with zero responsibility change.

---

## 24. Technical debt must be visible

**Principle:** Silent shortcuts are loans with compound interest.

**Why it exists:** Hidden debt becomes permanent architecture by accident.

**Good:** Visible debt tags, linked removal step, charter compliance.

**Bad:** “Temporary” boost logic still in production five years later.

---

## 25. Automation amplifies discipline

**Principle:** Automate repetition; never automate bypassing principles.

**Why it exists:** CI that enforces guards scales trust. Scripts that disable tests scale rot.

**Good:** Golden suite on every answer-path change; ADR template required for boundary changes.

**Bad:** Auto-merge without parity because “staging felt fine.”

---

## 26. Security protects trust

**Principle:** Protect observations, traces, and admin surfaces — knowledge systems are high-value targets.

**Why it exists:** Leaked traces expose site content; compromised admin can destroy trust at scale.

**Good:** Least privilege, secrets never in source, audit on understanding exports.

**Bad:** Debug endpoints that dump full memory in production without auth.

---

## 27. User experience is calibrated speech

**Principle:** UX is not polish on wrong answers — it is the right speech act, clearly.

**Why it exists:** Users experience **answers**, not pipelines. Refusal with explanation beats fluent fabrication.

**Good:** Completeness disclaimers, conflict transparency, fast refusal when evidence absent.

**Bad:** Hiding uncertainty to reduce support tickets.

---

## 28. Scalability is epistemic first

**Principle:** Scale claim integration, tension resolution, and reasoning — not just indexed rows.

**Why it exists:** Massive indexes that lie confidently are worse than smaller honest ones.

**Good:** Consolidation, merge/split, agenda equilibrium on mature sites.

**Bad:** Sharding search while Memory is a single unmaintained blob of state.

---

## 29. Evolution is migration, not revolution

**Principle:** The platform grows by strangler steps — each releasable, each reversible.

**Why it exists:** Big-bang rewrites discard production learning and usually fail.

**Good:** Passthrough → shadow memory → cutover — flags documented, parity proven.

**Bad:** “Stop the world for v2 rewrite.”

---

## 30. Culture is principled disagreement

**Principle:** Challenge requests that violate principles — including from leadership.

**Why it exists:** The cost of a bad architectural yes is paid for years. The cost of a respectful no is minutes.

**Good:** “That belongs in Maintenance, not Reasoning — here’s why.”

**Bad:** Silent compliance with a harmful shortcut because the ticket was urgent.

---

# Part II — Zero Hardcode Manifesto

## What hardcoding means

Hardcoding is **encoding business or site-specific truth in code or admin tables** instead of letting it emerge from observations and epistemic memory.

| Form | Example |
|------|---------|
| Industry-specific logic | Financial preset templates baked into core |
| Manual boosts / penalties | Intent → page-type weight maps |
| Manual mappings | Topic → document type tables |
| Page categories as cognition | Page role drives canonical selection |
| Business rules in code | “Career pages always deprioritized” |
| Customer-specific heuristics | URL patterns for one deployment |
| Magic constants | Hidden score adjustments in routing |
| Configuration as intelligence substitute | Sliders that exist because inference failed |

## Why hardcode is missing intelligence

Hardcode is not finished architecture. It is **evidence that the engine could not infer**.

Each rule freezes one customer’s world into the platform. The next site inherits another company’s ontology. Operators tune instead of the system learning. Tests encode accidents as laws. The platform stops getting smarter and starts getting **more configurable**.

Hardcode feels fast. It taxes **every future site forever**.

## When hardcoding is acceptable

Rarely, and only when **all** apply:

1. **Structural, not semantic** — e.g. stripping cookie banners is not “knowing an industry”
2. **Explicitly bounded** — documented, flagged, with removal criteria
3. **Not on the epistemic hot path** — does not decide what the site asserts or what answers ship
4. **Time-boxed** — visible debt entry and documented removal path

When in doubt: **it is not acceptable.**

---

# Part III — AI Principles

These principles govern how intelligence behaves on this platform. They extend the mandatory ten — not replace them.

| Principle | Meaning |
|-----------|---------|
| **Inference over configuration** | Discover structure from observations; resist admin knobs as product features |
| **Evidence over heuristics** | Heuristics are temporary scaffolding; evidence-backed claims are the goal |
| **Learning over hardcoding** | Each release should need fewer special cases than the last |
| **Generalization over specialization** | One engine for unknown sites beats ten industry templates |
| **Emergent behavior over manual rules** | Let concept regions, tensions, and agendas emerge from memory |
| **Reasoning over retrieval** | Search is a tool the mind uses — not the mind itself |
| **Understanding over similarity** | Nearest-neighbor is a candidate generator, not a conclusion |
| **Truthfulness over confidence** | Calibrated speech beats fluent guessing |
| **Explainability over cleverness** | A clear “why not” beats an opaque “why yes” |
| **Automation over user configuration** | Reduce operator work through intelligence, not through more settings |

**Challenge these when reality demands it** — but only through ADR, with evidence that the platform long-term benefits.

---

# Part IV — Product Principles

Engineering exists to improve the product. Every implementation should improve **at least one** of:

| Dimension | Meaning |
|-----------|---------|
| **Answer quality** | More correct, complete, scoped to the site |
| **Trust** | Calibrated honesty, refusal when needed |
| **Explainability** | Humans see why, not scores |
| **Performance** | Latency, cost — without lying faster |
| **Generalization** | Next unknown site works with less ops |
| **Automation** | Less manual profile and tuning work |
| **Maintainability** | Clearer boundaries, less coupling |
| **Simplicity** | Fewer concepts, fewer knobs, fewer exceptions |

If a change improves **none** of these, question whether it should exist.

Features that only improve developer convenience **today** at product cost **tomorrow** are negative value.

---

# Part V — Performance Philosophy

Performance is a feature — not an afterthought, not a post-release surprise.

Every feature should declare, before merge:

| Impact | Question |
|--------|----------|
| **Latency** | How much does this add to answer time? |
| **Memory** | What new resident state does this require? |
| **Token usage** | Does this increase context sent to language generation? |
| **Storage** | What new persistent state grows per site, per page, per claim? |
| **Background processing** | What new scheduled or event-driven work does this add? |

No feature should **silently** degrade performance. If cost is unavoidable, make it **visible** — in diagnostics, in operator docs, in release notes.

Speed without honesty is not a win. Honesty at acceptable speed is.

---

# Part VI — Simplicity Rule

If a feature requires:

- multiple configuration screens,
- user training,
- complex documentation,
- special cases,
- exception-heavy logic,

**stop.** Challenge the design.

The best feature is one users never have to configure. The best operator experience is one where the engine discovers what used to require a preset. The best codebase is one where new engineers understand boundaries without a tour guide.

When simplicity and speed conflict, **simplicity wins** unless production safety requires otherwise — and then the debt is visible.

---

# Part VII — Engineering Values

These values define how we show up in code review, incidents, and design discussions:

| Value | We mean |
|-------|---------|
| **Humility** | The system doesn’t know truth — only what the site asserts |
| **Evidence** | Claims require justification; so do we |
| **Curiosity** | Disciplined attention to tension — not random exploration |
| **Ownership** | You protect the platform, not only your PR |
| **Honesty** | Weak evidence and conflict are spoken |
| **Long-term thinking** | Five-year coherence beats five-hour hacks |
| **Production discipline** | Flags, rollbacks, golden tests, runbooks |
| **Reliability** | Stable beats clever under load |
| **Clarity** | The next engineer understands without oral tradition |
| **Integrity** | We do not ship what we would not defend in an incident review |

---

# Part VIII — Quick reference

| Topic | Principles |
|-------|------------|
| Architecture | 8, 9, 10, 11, 12, 29 |
| Knowledge | 1, 13 |
| Reasoning | 3, 7 |
| Evidence | 2, 14 |
| Memory | 13, 14, 15 |
| Maintainability | 11, 20, 23, 24 |
| Technical debt | 24, Zero Hardcode |
| Testing | 20, 18 |
| Production | 18, 19 |
| Security | 26 |
| Performance | 21, Part V |
| Observability | 18, 22 |
| Scalability | 28, 16 |
| Explainability | 17, 7 |
| Automation | 25 |
| User experience | 27, 7 |
| Migration | 29 |
| Refactoring | 23, 11 |
| Long-term evolution | 5, 16, 29 |
| Engineering culture | 30, Part VII |

---

# Part IX — A message to future engineers

You are joining a project that refused to become another search-and-summarize wrapper.

That refusal is not snobbery. It is a bet: **websites contain knowledge**, and software can form honest, revisable opinions about what they communicate — without an army of operators tuning rules for each industry.

You inherit frozen architecture not to constrain you, but to **free** you. The hard arguments — what knowledge is, how memory evolves, how curiosity maintains itself — were fought once. Your job is to **execute with discipline** and **protect** what was decided, not relitigate it every sprint.

### Why architecture matters

Architecture is where truth lives. When boundaries blur, intelligence becomes configuration. When subsystems merge, replaceability dies. When hacks accumulate, nobody knows which layer decides what the site “knows.” A platform without architectural discipline does not fail loudly — it **slowly stops being intelligent**.

### Why shortcuts accumulate

Each shortcut feels small. One industry heuristic. One manual boost. One “temporary” bypass. None alone destroys the platform. Together they teach the codebase that **rules are easier than reasoning**. Operators start tuning instead of trusting. New sites need more setup, not less. The engine “knows” customers instead of discovering knowledge. Eventually someone proposes a rewrite — and the rewrite throws away years of production learning. The cycle repeats.

### Why intelligent systems become unintelligent

Intelligent systems fail when engineering discipline is lost — not when models change. They fail when evidence is optional, when confidence replaces truthfulness, when retrieval replaces reasoning, when hardcode replaces learning. They fail when nobody says no to the urgent ticket that violates a boundary. They fail when debt is invisible and tests protect the wrong things.

Architectural discipline is how we break that cycle.

When you improve claim extraction, surface tensions faster, make refusals rare **and** trustworthy, or clarify a subsystem boundary — you make the platform **smarter, cleaner, and easier to evolve**. That is the job. Not the most lines. Not the cleverest abstraction. Not the loudest demo.

If you find a genuine flaw: **stop. Write an ADR. Make the case.** We change the frozen model rarely — but we do change it when reality demands honesty.

If you find no flaw: implement beautifully inside the boundaries. Test what matters. Declare performance impact. Flag what’s risky. Mark what’s debt. Ship in releases someone can roll back at 3 a.m.

Ten years from now, this platform should still read like one mind — careful, honest, curious within bounds, ruthless about hardcode, kind to operators, respectful of users who deserve truth more than fluency.

Build like that.

---

## Related documents

| Document | Role |
|----------|------|
| `ENGINEERING_MANIFEST.md` | Non-negotiables and STOP workflow |
| `RFC-0001-KNOWLEDGE-OS-CORE.md` | Product identity |
| `COGNITIVE_ARCHITECTURE.md` | What the system knows |
| `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md` | Curiosity and maintenance |
| `KNOWLEDGE_OS_ARCHITECTURE_v1.md` | Subsystem boundaries |
| `RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` | How we migrate safely |
| `DEVELOPMENT_CHARTER.md` | How we collaborate day to day |
| `docs/adr/` | Rare boundary changes |

**This document does not replace those. It tells you how to think while using them.**
