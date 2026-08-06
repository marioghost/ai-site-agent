# Evidence Planning Architecture

Status: **Release 1.0 internal evolution** (replaces score-only final ordering).

Historical audit reports remain valid as failure analysis; this document describes
the post-evolution architecture.

## Problem (old failure mode)

The previous pipeline implicitly decided final context through scattered steps:

1. retrieval + rerank (mixed scores)
2. broad-page inject with synthetic scores
3. canonical / profile reorder
4. rigid semantic tiers
5. context builder score sort
6. budget trim

Failures observed in production diagnostics:

- Injected broad sources could outrank authoritative evidence on numeric score alone
- Document relevance did not guarantee section relevance
- Authority, coverage, diversity, sufficiency, and budget were not first-class
- Diagnostics could not fully explain final evidence order

Magic score caps and global tier enums were stabilization patches, not architecture.

## New pipeline

```
query understanding
  → retrieval candidate pool (DFP / EA — unchanged retriever)
  → evidence normalization
  → intent-aware authority fitness
  → answer-aspect planning
  → coverage-aware selection
  → diversity / redundancy control
  → section-level selection
  → sufficiency + contradiction assessment
  → budget-aware packing
  → context serialization (RetrievalContextBuilder)
  → prompt assembly
  → generation
  → post-answer evidence sufficiency (Reasoning — unchanged contract)
```

## Ownership boundaries

| Component | Owns | Does not own |
|-----------|------|--------------|
| `DocumentFirstRetrievalPipeline` | Chunk retrieval, document scoring, rerank candidates | Final context order |
| `RetrievalPipelineService` | Stage coordination, broad inject as candidates | Final selection policy |
| **`EvidencePlanner`** | **Final evidence selection, order, sufficiency, packing** | Retrieval, LLM |
| `RetrievalContextBuilder` | Serialize selected evidence to prompt text | Re-ranking |
| `CompactPromptBuilder` | User prompt framing | Evidence selection |
| `assess_evidence_sufficiency` | Post-answer advisory status | Pre-LLM planning |

## Normalized candidate model

`EvidenceCandidate` (internal, not persisted) carries:

- identifiers, URL, title, heading, text
- document type, page role, source purpose
- retrieval scores, inject provenance
- KP preferred/deprioritized flags, canonical
- authority fitness + explainable factors
- inferred evidence aspects, section selection, token estimate

## Authority fitness

Authority is conditional: `intent × purpose × role × KP × answerability`.

Continuous fitness score in `[0, 1]` with diagnostic bands (`high`, `moderate`, `low`, `poor`).
No global “homepage is bad” rule. No synthetic score caps as architectural control.

## Answer-aspect planning

Deterministic aspect templates derived from `QueryUnderstanding` / intent:

- overview → identity, activity (+ optional capabilities)
- procedure → steps (+ optional prerequisites)
- policy → rule, scope
- product → product_identity (+ optional pricing)
- news/offer intents → current_item / offer

Forbidden aspects suppress incidental sources for unrelated intents.

## Coverage optimizer

Greedy selection by **marginal value**:

- authority fitness
- new required-aspect coverage
- optional aspect coverage
- section relevance
- redundancy penalty

Prefers complementary evidence over near-duplicate high scores.

## Diversity and redundancy

- Max chunks per source
- Duplicate group limits
- Language duplicate preference
- Injected broad sources must justify unique aspect coverage when stronger natural evidence exists

## Sufficiency (pre-LLM)

`EvidencePlanSufficiency`: `sufficient | partial | weak | no_evidence`

Feeds diagnostics; post-answer `EvidenceSufficiencyAssessment` remains the product contract.

## Context budget

Uses actual operator system prompt + user framing tokens. Packing drops redundant
and optional evidence before critical unique aspects.

## Diagnostics

`RetrievalDiagnostics.evidence_plan` mirrors planner decisions:

- knowledge plan, candidates, fitness factors
- selected/rejected with reasons
- sufficiency, contradictions, packing decisions
- final order URLs

## Anti-hardcoding rules

- No tenant URLs, industries, or languages in production selection logic
- KP/SI configuration is input, not bypass
- Regression fixtures may use specific URLs; production code may not

## Migration implications

- **No reindex required** — uses existing metadata and content
- Optional reindex improves section headings quality, not correctness
- Old `source_authority.py` tier ordering removed; selection owned by `EvidencePlanner`

## Extension rules

New intents → extend aspect templates and role/intent fitness maps generically.
New document types → map to generic roles/purposes via Source Intelligence.
Do not add per-tenant ordering branches.
