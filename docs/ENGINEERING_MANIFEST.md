# AI Site Agent — Engineering Principles & Architecture Manifest

You are not building another RAG application.

You are building an **Autonomous Knowledge Intelligence Engine**.

Every architectural decision must move the system closer to **understanding knowledge** instead of executing predefined rules.

**North-star vision:** `docs/KNOWLEDGE_INTELLIGENCE_ENGINE.md`  
**Engineering philosophy (timeless):** `docs/ENGINEERING_PRINCIPLES.md`  
**Cognitive architecture (foundational):** `docs/COGNITIVE_ARCHITECTURE.md`  
**Active acquisition:** `docs/RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md`  
**Engineering architecture (v1 contract):** `docs/KNOWLEDGE_OS_ARCHITECTURE_v1.md`  
**Production migration (execution):** `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md`  
**Development charter (how we work):** `docs/DEVELOPMENT_CHARTER.md`  
**Architecture RFC:** `docs/RFC-0001-KNOWLEDGE-OS-CORE.md`  
**Migration roadmap:** `docs/MIGRATION_ROADMAP_KNOWLEDGE_OS.md`

This document defines the permanent engineering principles of the entire project.

These principles override convenience, shortcuts and temporary fixes.

---

## Mission

The mission of this project is to build an AI system that can understand **ANY** website with minimal human intervention.

The system must work equally well for:

- banks
- e-commerce
- SaaS
- documentation
- healthcare
- education
- government
- support portals
- corporate knowledge bases
- internal enterprise systems

The administrator should not need AI expertise, Retrieval expertise or prompt engineering knowledge.

The platform must do the difficult work automatically.

---

## Core Philosophy

**The system should understand knowledge.**

**It should NOT understand configurations.**

If solving a problem requires another configuration screen, another boost value, another category, another manual mapping or another rule — **stop**. Redesign the architecture instead.

- Configuration is a last resort.
- Automatic understanding is always preferred.

---

## Absolute Rule #1 — Never Hardcode Business Knowledge

Never. No exceptions.

Do not hardcode:

- industries
- page categories
- document priorities
- retrieval boosts
- penalties
- topic mappings
- business rules
- URL patterns
- bank-specific logic
- e-commerce logic
- healthcare logic
- documentation logic
- manually maintained ontologies

If you feel the need to introduce a hardcoded rule, stop and ask:

> What architectural capability is missing that makes this rule necessary?

Implement that capability instead.

---

## Absolute Rule #2 — The Administrator Should Never Understand Retrieval

Never expose:

- boost values
- ranking coefficients
- document priorities
- semantic thresholds
- embedding settings
- reranker weights
- manual page classifications
- topic mappings
- complex AI settings

The system should configure itself.

---

## Absolute Rule #3 — Every Improvement Must Increase Autonomy

Never more manual.

---

## Zero Hardcode Policy

Hardcoded logic is **technical debt**.

Whenever you are about to introduce:

- `if` statements based on business domains
- static mappings
- predefined categories
- manual heuristics
- special-case handling
- administrator tuning to compensate for missing intelligence

**STOP.**

Do not implement the workaround.

Instead:

1. Identify the missing architectural capability.
2. Implement the capability.
3. Solve the problem through inference.

The goal is **not** to make the current website work.

The goal is to make the engine capable of understanding **ANY** website automatically.

When in doubt:

- Prefer **intelligence** over configuration.
- Prefer **inference** over rules.
- Prefer **architecture** over patches.
- Prefer **generic solutions** over domain-specific solutions.

Every hardcoded rule should be treated as a **bug in the architecture**, not as a feature.

---

## Knowledge-First Architecture

The website is not a collection of pages. The website is a **knowledge ecosystem**.

Pages are only **evidence containers**. Knowledge is the objective.

The engine should build an internal mental model — like a human expert reading the entire site:

- concepts, entities, relationships
- central vs secondary knowledge
- what explains, summarizes, or contradicts what
- evidence, authority, duplicates, gaps, uncertainty
- how understanding evolves over time

This understanding lives in **Knowledge Memory** and is used by **Knowledge Reasoning** at query time. Retrieval is a tool inside reasoning — not the architecture center.

See `docs/KNOWLEDGE_INTELLIGENCE_ENGINE.md` for the full mental model.

---

## Source Intelligence

Source Intelligence should **not** classify pages using predefined business categories.

Instead it should infer:

- What knowledge exists here?
- Which concepts are explained?
- Which entities appear?
- Which questions can this page answer?
- Which questions should not use this page?
- How trustworthy is it?
- How complete is it?
- How unique is it?
- How authoritative is it?
- How much boilerplate exists?
- How much navigation exists?
- How much evidence exists?
- What other pages support the same knowledge?

Everything should be inferred.

---

## Knowledge Understanding

The goal is **semantic understanding** of indexed knowledge — not building a graph.

A knowledge graph is only one possible internal representation. Embeddings, vectors, clusters, concept indexes, summaries, and relational models are equally valid. Choose whatever representation best helps the system understand the knowledge. Never build structures for their own sake.

The system should continuously deepen its understanding of what a site knows:

- concepts
- entities
- relationships
- authority and canonical sources
- supporting and duplicate evidence
- semantic clusters
- knowledge coverage and gaps

This understanding should emerge automatically and evolve as new content is indexed.

Internal representations are **implementation details** behind a stable understanding interface. The engine must be **architecture-driven**, not **graph-driven**.

---

## Query Understanding

Do not map queries to document types.

Understand the user's **information need**. Infer automatically:

- intent
- topic
- expected answer
- required evidence
- required confidence
- required coverage
- ambiguity
- language

Then resolve that need against the site's **semantic understanding** — not against pages, chunks, or a predefined structure.

---

## Retrieval

Retrieval should retrieve **knowledge**. Not pages. Not chunks. Not URLs.

Documents are evidence containers. Knowledge is the target.

**Retrieval is a consequence of understanding** — not a search technique applied independently.

```
User
  ↓
Knowledge Reasoning
  ↓
Knowledge Memory (what the site knows)
  ↓
Evidence Assembly (retrieval as tool)
  ↓
Context Builder
  ↓
LLM
```

Knowledge Understanding and Knowledge Memory may use graphs, indexes, embeddings, or hybrids internally. Callers and administrators do not depend on which representation is used.

---

## Automatic Learning

The system should improve automatically as more content is indexed:

- discover new concepts
- merge duplicate concepts
- improve canonical detection
- improve evidence quality
- improve semantic relationships (regardless of internal representation)
- improve semantic clusters
- improve overall understanding coverage

No manual retraining. Prefer improving understanding quality over adding new internal structures.

---

## No Manual Tuning

Do not solve problems by introducing:

- another slider
- another checkbox
- another configuration page
- another weight
- another threshold
- another mapping
- another boost
- another penalty

Instead improve inference.

---

## Explainability

The system should explain itself — not with numbers, with **reasoning**.

Examples:

- "This source was selected because it directly answers the user's question."
- "This page was ignored because it mostly contains navigation."
- "This information is supported by multiple independent sources."
- "This page contains duplicate knowledge already covered elsewhere."

Reasoning should be understandable.

---

## Code Quality

**Prefer:**

- generic algorithms
- semantic inference
- self-discovery
- modularity
- knowledge extraction
- statistical reasoning
- graph reasoning
- pattern discovery
- machine understanding

**Avoid:**

- `if (bank)` / `if (shop)` / `if (product)`
- `switch(documentType)`
- manual mappings
- static lookup tables
- industry rules
- URL-based assumptions
- page-type assumptions

---

## Future Thinking

Every architectural decision should answer:

> Will this still work if the next customer is completely different?

If the answer is **no**, the design is wrong.

---

## Engineering Checklist

Before writing code ask:

- Can this be inferred instead of configured?
- Can this be discovered instead of hardcoded?
- Can this be learned instead of mapped?
- Can this emerge from the indexed knowledge?
- Will this work for any industry?
- Does this reduce administrator effort?
- Does this make the platform smarter?

If any answer is **no**, redesign the solution.

---

## Final Principle

We are **NOT** building another chatbot.

We are **NOT** building another RAG.

We are building an **Autonomous Knowledge Intelligence Engine**.

Every commit should move the project closer to that vision.
