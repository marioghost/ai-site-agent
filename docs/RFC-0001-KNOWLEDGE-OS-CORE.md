# RFC-0001: Knowledge OS Core

**Status:** Accepted  
**Scope:** Autonomous Knowledge Intelligence Architecture  
**Supersedes:** retrieval-centric and graph-centric framing as architecture drivers

Everything built after this RFC must follow these principles.

Related: `KNOWLEDGE_INTELLIGENCE_ENGINE.md`, `ENGINEERING_MANIFEST.md`, `COGNITIVE_ARCHITECTURE.md`, `RFC-0002-ACTIVE-KNOWLEDGE-ACQUISITION.md`

---

## Project identity

This project is **NOT**:

- another chatbot
- another RAG
- another vector search engine
- another embedding database
- another retrieval pipeline

This project is a **Knowledge Operating System**.

Its purpose is to autonomously **understand**, **organize**, **maintain**, and **reason** over the knowledge of any website.

| Interface | Role |
|-----------|------|
| Chat | One interface |
| Search | One interface |
| Analytics | One interface |
| **Knowledge OS** | **The product** |

---

## Primary objective

The platform must autonomously build an internal understanding of any website **without**:

- industry templates
- manual ontology
- business-specific code
- manual mappings
- page categories
- retrieval tuning
- administrator expertise

The administrator should only provide:

```
Website URL → Index → (everything else emerges automatically)
```

---

## The website is not a set of pages

Pages are only **observations**.

The engine should discover: knowledge, relationships, concepts, entities, facts, evidence, uncertainty, authority, coverage, contradictions, duplicates, gaps.

**Instead of indexing pages, the engine should index understanding.**

---

## Knowledge acquisition

Each indexed page should contribute knowledge to global memory.

Never think: *"I indexed another page."*  
Think: *"I learned something new."*

The engine must continuously ask:

- Did I discover a new concept?
- Did I strengthen an existing concept?
- Did I contradict existing knowledge?
- Did I discover a better explanation?
- Did I discover a more authoritative source?
- Did I discover duplicated knowledge?
- Did I discover missing knowledge?

Knowledge acquisition is **incremental**.

---

## Knowledge Memory

Continuously evolving semantic memory. **Does not store pages — stores understanding.**

| Memory contents |
|-----------------|
| Concepts, entities, facts, definitions |
| Relationships, evidence, confidence, coverage |
| Alternative explanations |
| Supporting / contradicting evidence |
| Unknowns |

Internal representation (graph, index, embeddings) is implementation detail.

---

## Knowledge Reasoning

When the user asks a question, the engine **reasons**:

```
Understand the user's information need
  ↓
Understand what knowledge is required
  ↓
Locate relevant concepts
  ↓
Gather supporting evidence
  ↓
Evaluate evidence quality
  ↓
Detect missing evidence
  ↓
Assemble an answer
  ↓
Explain confidence
```

Searching is only one possible step.

---

## No hardcode policy

Hardcoded logic is an **architectural failure**.

Never implement: `if(domain)`, `if(bank)`, `if(shop)`, `if(document_type)`, `if(category)`, `if(page_role)`, manual boosts/penalties/weights/mappings/business rules/ontologies/retrieval tuning/prompt branching.

**STOP** → identify missing intelligence capability → implement capability.

---

## Discovery over configuration

The engine must **discover**, not be configured.

**Prefer:** semantic inference, probabilistic reasoning, statistical evidence, knowledge extraction, pattern discovery, relationship discovery, concept emergence, cluster evolution, uncertainty estimation.

**Avoid:** configuration, manual labels, business heuristics, rule engines, administrator tuning.

---

## Knowledge is dynamic

Automatically: merge/split concepts, detect obsolete/conflicting knowledge, update confidence, discover canonical sources and new evidence.

---

## Every component must learn

| Component | Learns |
|-----------|--------|
| Crawler | Website structure |
| Indexer | Content quality |
| Knowledge Intelligence | Concepts |
| Retrieval (as service) | Evidence quality |
| Analytics | Usage patterns |

The system becomes more intelligent after every indexing run.

---

## Retrieval is not the core

Retrieval is a **service**, not the architecture. Optimize **understanding**. Retrieval improves because understanding improves.

---

## Diagnostics

Explain **thinking**, not implementation.

| Not this | This |
|----------|------|
| Dense Score, Lexical Score, Boost, Penalty | What knowledge was needed? |
| | Why was this source selected? |
| | What evidence supports/rejects it? |
| | How certain is the system? |
| | What knowledge is missing? |

---

## Self-evaluation

Every answer internally evaluates:

- Enough evidence?
- Independent evidence?
- One weak page?
- Contradictory evidence?
- More authoritative source?
- Answer or admit uncertainty?

Confidence emerges from evidence quality.

---

## Future evolution

Architecture must support without redesign: continuous indexing, multiple websites, enterprise knowledge, cross-site reasoning, tool calling, autonomous agents, scheduled learning, knowledge versioning, temporal reasoning, multilingual understanding.

---

## Architectural decision rule

Before writing code:

1. Does this make the engine smarter?
2. Does this reduce manual work?
3. Does this increase understanding?
4. Does this work for unknown websites?
5. Can this emerge automatically?
6. Will this work for industries we have never seen?

If **NO** → redesign. Never compensate with configuration.

---

## The golden rule

The engine should not know it is indexing a bank, store, or university.

It should know it has **discovered knowledge** — concepts, relationships, evidence.

The engine should never think in terms of websites. It should think in terms of **knowledge**.

---

## Implementation mandate

Review the entire codebase. For every subsystem identify:

- Where code assumes documents instead of knowledge
- Where retrieval is treated as primary architecture
- Where hardcoded business assumptions exist
- Where admin configuration compensates for missing intelligence
- Where information is stored instead of understood

Produce a migration roadmap. Refactor incrementally. Do not rewrite everything.

### Evolution path

```
Document-centric
  ↓
Retrieval-centric
  ↓
Knowledge-centric
  ↓
Understanding-centric
```

Maintain backward compatibility. After each phase document: architecture changes, reasoning, expected improvements, migration safety, risks, tests.

**Never introduce new technical debt while implementing this vision.**

---

## Migration roadmap

**Codebase audit and phased plan:** `docs/MIGRATION_ROADMAP_KNOWLEDGE_OS.md`  
**Full architecture review:** `docs/ARCHITECTURE_REVIEW_KNOWLEDGE_OS.md`

Evolution path:

```
Document-centric → Retrieval-centric → Knowledge-centric → Understanding-centric
```

Refactor incrementally. Maintain backward compatibility. Never introduce new technical debt while implementing this vision.
