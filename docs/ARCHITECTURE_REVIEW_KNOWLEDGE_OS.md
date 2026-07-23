# Knowledge OS Architecture Review

**Status:** Architecture review only — no implementation  
**Date:** 2026-07-04  
**Lens:** RFC-0001, `KNOWLEDGE_INTELLIGENCE_ENGINE.md`, `SEMANTIC_UNDERSTANDING_MVP.md`  
**Constraint:** This report does not authorize new hardcode, boosts, categories, or admin knobs.

---

## 1. Executive summary

The platform is **not a normal RAG system** in aspiration, but **still operates as one in production**. The codebase sits in a **hybrid transitional state**: a deliberate move from chunk-level document-type boosting toward document-first retrieval with semantic compatibility scoring — while retaining a large **rule-and-config compensation layer** from the earlier architecture.

### Overall maturity

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Document-centric storage | **Dominant** | `Source` / `Chunk` are the knowledge artifacts |
| Retrieval-centric orchestration | **Dominant** | Chat = cache → retrieve → rank → LLM |
| Knowledge-centric signals | **Partial** | Per-page Source Intelligence JSON |
| Understanding-centric reasoning | **Absent** | No Knowledge Memory, no reasoning layer |

**Closest to the vision:** `QueryUnderstandingService`, `SemanticCompatibilityScorer`, `ExplanationBuilder`, simplified retrieval presets (Automatic/Fast/Balanced/High Precision), removal of doc-type boosts from production hybrid fusion.

**Farthest from the vision:** Industry presets (`bank_financial`, etc.), Knowledge Profile boost tables, document-type ontology driving canonical/importance, admin-facing retrieval tuning, bank-biased entity extraction in profile generation.

### Critical finding

The system has **two parallel intelligence models** that do not fully connect:

1. **Knowledge Profile rules** — URL patterns, document-type priorities, industry presets (mostly **legacy**, partially used for canonical selection and diagnostics)
2. **Source Intelligence profiles** — per-page semantic JSON (used by **production scoring** via `SemanticCompatibilityScorer`)

`build_boost_tables()` and several settings JSON columns are **implemented but disconnected** from the production scorer — creating false confidence that admin tuning still drives ranking.

### Recommended next step

**Phase 1 (Cleanup and visibility)** — no new features. Deprecate and document legacy rule paths, improve diagnostics toward semantic reasoning, mark manual tuning as legacy. Then **Phase 2 (Knowledge Intelligence layer)** — aggregate SI into site-wide understanding before touching chat orchestration.

---

## 2. Current architecture overview

### Production query path (simplified)

```
User query
  ↓
RagService / RagStreaming
  ↓ normalize, cache lookup
  ↓
RetrievalPipelineService
  ├── RetrievalIntentService → KnowledgeProfileService.match_intent()
  ├── QueryExpansionService
  ├── DocumentFirstRetrievalPipeline
  │     ├── HybridChunkRetriever (dense + lexical on chunks)
  │     ├── DocumentAggregator (group by source_id)
  │     ├── QueryUnderstandingService
  │     ├── DocumentScorer + SemanticCompatibilityScorer (SI-based)
  │     └── DocumentReranker + ExplanationBuilder
  ├── CanonicalSourceService (profile doc-type rules)
  ├── broad page injection (SI flags + hardcoded score deltas)
  └── RetrievalContextBuilder → page bodies
  ↓
CompactPromptBuilder (intent-template prompts)
  ↓
LLM → optional polish → ResponseValidator
  ↓
ChatResponseBuilder + diagnostics
```

### Index path (simplified)

```
URL → Crawler → IndexingService
  ├── extract text, detect document_type (profile URL rules)
  ├── chunk → embed → Qdrant
  └── mark needs_intelligence
  ↓
SourceIntelligenceGenerationService (async or inline)
  ├── rules fallback from document_type/page_role
  └── optional LLM semantic profile
  ↓
Source row updated (per-page metadata only — no site-wide memory)
```

### Architectural identity gap

| What RFC says | What code does |
|---------------|----------------|
| Index understanding | Index chunks + label document_type |
| Reason, then retrieve | Retrieve, then prompt |
| Knowledge Memory | Per-page SI JSON on `Source` |
| Admin provides URL only | Admin edits Knowledge Profile, boosts, presets |
| Domain-agnostic | `bank_financial` preset, bank entity regex |

### Positive trajectory (do not discard)

- Document-first pipeline is production path; legacy `HybridRetrievalService` is test-only
- Scoring uses semantic compatibility, not admin weight JSON
- Human-language `why_selected` / `why_rejected` exist in reranker
- Retrieval presets collapsed to simple modes

---

## 3. Hardcode audit

Severity: **H** = high (domain/taxonomy drives behavior), **M** = medium (generic but rule-driven), **L** = low (structural/ops)

### 3.1 Document type & page role taxonomy

| Sev | File | Symbol | What is hardcoded | Problem | Replace with |
|-----|------|--------|-------------------|---------|--------------|
| H | `source_intelligence_constants.py` | `GENERIC_DOCUMENT_TYPES`, `DOCUMENT_TYPE_TO_ROLE`, `CANONICAL_DOCUMENT_TYPES`, `LOW_OVERVIEW_*` | 20+ fixed page categories | Canonical, importance, answer flags derive from type tables | Authority from evidence graph: coverage, corroboration, query success |
| H | `source_intelligence_service.py` | `_importance()`, `_answer_flags()`, `_is_canonical()` | Score deltas by document_type/page_role | Bank-agnostic but still taxonomy-driven | Inferred importance from content quality + concept centrality |
| M | `source_semantic_rules.py` | `_ROLE_TO_PURPOSE`, `_DOC_TYPE_TO_ENTITY`, `_ROLE_TO_INTENTS` | Role→purpose/intent lookup tables | Rules fallback collapses to page taxonomy when LLM off | Open-vocabulary extraction; uncertainty when thin |
| M | `schemas/source_intelligence.py` | `GENERIC_DOCUMENT_PURPOSES`, `GENERIC_ENTITY_TYPES`, `GENERIC_SUPPORTED_INTENTS` | Closed-world frozensets | Gates validation; prevents emergent vocabulary | Loose validation; site-specific concepts |
| M | `indexing_service.py` | `detect_document_type()` | URL/title/heading substring rules via profile | Labels baked into every chunk at index time | Post-index semantic purpose; chunks as evidence pointers only |

### 3.2 Industry & domain assumptions

| Sev | File | Symbol | What is hardcoded | Problem | Replace with |
|-----|------|--------|-------------------|---------|--------------|
| H | `knowledge_profile_service.py` | `PRESETS`, `bank_financial_profile()` | 7 industry presets; bank entity_type, rates/credits topics | Violates golden rule — engine "knows" it's a bank | Auto-generated understanding from content clusters only |
| H | `knowledge_profile_generation/structure_analyzer.py` | `_TYPE_KEYWORDS`, `_CATEGORY_PATTERNS` | Detects `bank_financial`, URL segments (rates, loans, cards) | Industry detection by keyword | Statistical site character from content |
| H | `knowledge_profile_generation/entity_extractor.py` | `_ENTITY_PATTERNS` | Bank product regex (credit card, mortgage, ATM, Visa…) | Domain-specific entity extraction | SI LLM + emergent entities from content |
| H | `knowledge_profile_generation/profile_assembler.py` | Preset seeding | Seeds from `PRESETS["bank_financial"]` etc. | Generated profile inherits industry template | Output discovered concepts only |
| M | `knowledge_profile_service.py` | `_generic_document_type_rules()` | Patterns like `about-bank`, `pro-bank`, `курси-валют` | URL heuristics for page classification | Semantic purpose from SI |

### 3.3 Intent & routing frozensets

| Sev | File | Symbol | What is hardcoded | Problem | Replace with |
|-----|------|--------|-------------------|---------|--------------|
| M | `source_intelligence_router.py` | `OVERVIEW_INTENTS`, `PRODUCT_INTENTS`, … + language boosts (+0.08/-0.06) | Intent class → boost/penalty | Rule engine on top of compatibility | Query→concept resolution; no manual boosts |
| M | `retrieval_engine/query_understanding.py` | `_LISTING_MARKERS`, `_purpose_expectations()` | Regex + purpose maps | Answer type → predefined purposes | Infer evidence needs from query semantics + site memory |
| M | `retrieval_engine/prompt_builder.py` | `OVERVIEW_INTENTS`, `LISTING_INTENTS`, `SUPPORT_INTENTS` | Intent → prompt template | Prompt branching by intent slug | Template from resolved knowledge need + evidence type |
| M | `knowledge_profile_service.py` | `GENERIC_OVERVIEW_PATTERNS`, `match_intent()` | UA/EN phrase lists + heuristics | Static intent detection | Learned intent clusters from queries + content |
| M | `broad_question_service.py` | `_STRUCTURAL_BROAD_MARKERS`, `injection_queries()` | Broad markers + preferred doc types | Page-type injection list | Concept coverage gap detection |

### 3.4 Boost, penalty & scoring constants

| Sev | File | Symbol | What is hardcoded | Problem | Replace with |
|-----|------|--------|-------------------|---------|--------------|
| M | `knowledge_profile_service.py` | `build_boost_tables()`, `SourcePriorityRule` | Intent→boost/deprioritize doc types (-0.28, -0.20) | **Not wired to production scorer** — dead/confusing | Remove or replace with understanding-based routing |
| M | `content_category_service.py` | `category_boost()` | Profile priority math | **Never called in production** | Delete or wire through understanding layer |
| M | `document_scorer.py` | `_BLEND_*` constants | Fixed semantic/lexical/compat weights | Acceptable internally if not admin-tuned; still opaque | Evidence-quality-derived weighting; explainable blend |
| M | `semantic_compatibility.py` | Internal 0.30/0.30/0.25/0.15 blend | Fixed sub-scores | Same as above | Self-evaluation from evidence |
| M | `retrieval_pipeline_service.py` | `_inject_broad_pages()` | +0.48 base, +0.10 homepage, +0.08 canonical | Magic numbers on page flags | Inject when concept coverage gap detected |
| L | `hybrid_retrieval_service.py` | Fusion weights, `_STRUCTURED_BLOCK_BOOST` | Legacy chunk fusion | Test-only path | Delete after test migration |
| L | `source_intelligence_router.py` | `_compat_to_boost()` ±0.45 | Router boost mapping | Parallel boost path | Single understanding-based signal |

### 3.5 URL & regex classification

| Sev | File | Symbol | What is hardcoded | Problem | Replace with |
|-----|------|--------|-------------------|---------|--------------|
| M | `knowledge_profile_generation/structure_analyzer.py` | `_CATEGORY_PATTERNS` (17 categories) | URL segment → category | Navigation structure as ontology | Emergent sections from link graph + topics |
| M | `knowledge_profile_generation/topic_discovery.py` | `_STRATEGY_MAP` (loans, deposits, rates…) | Topic key → answer strategy | Banking topic assumptions | Strategy from evidence type + query outcomes |
| L | `source_intelligence_service.py` | `_site_section()` | First URL path segment | Weak semantics | Nav clustering / SI topics |
| L | `retrieval_engine/content_sanitizer.py` | `_UI_JUNK_PATTERNS` | UI noise regex | Acceptable structural cleanup | Keep |

### 3.6 Summary counts

| Category | Approx. files affected | Production impact |
|----------|------------------------|-------------------|
| Document type / page role taxonomy | 12+ | **High** — SI, indexing, canonical, context |
| Industry presets & bank logic | 6+ | **High** — profile generation, defaults |
| Intent frozensets & routing | 10+ | **Medium** — intent, prompts, router |
| Boost/penalty tables | 4 | **Low in scorer** — used in canonical/diagnostics |
| Fixed scoring blends | 3 | **Medium** — opaque but internal |
| URL/regex classification | 5+ | **Medium** — index-time labels |

---

## 4. Configuration audit

Settings that exist because the system is **not intelligent enough yet**.

### 4.1 Retrieval tuning (should not be user-facing)

| Setting | Why it exists | Problem it patches | Replace with |
|---------|---------------|-------------------|--------------|
| `title_match_boost`, `heading_match_boost` | Lexical retrieval misses semantic matches | Weak chunk ranking | SI compatibility + concept index |
| `homepage_boost_*`, `short_query_lexical_boost` | Homepage/short query under-ranking | Document-centric retrieval | Concept centrality in Knowledge Memory |
| `similarity_threshold` | Filter low-similarity chunks | Fixed cutoff for all query types | Adaptive threshold from confidence calibration |
| `minimum_retrieval_score` | Cut weak document candidates | Manual precision/recall | Evidence sufficiency from reasoning layer |
| `top_k`, `top_k_dense`, `top_k_lexical`, `document_limit` | Pipeline sizing | One-size-fits-all retrieval budget | Query-complexity-aware budget |
| `retrieval_mode` (dense/lexical/hybrid) | Admin picks search strategy | System can't choose | Auto-select from query characteristics |
| `retrieval_profile` presets | Latency vs precision tradeoff | Acceptable simplification if kept minimal | Usage + hardware-aware autonomous policy |
| `enable_intent_aware_retrieval` | Toggle intent pipeline | Intelligence is optional | Always-on reasoning |
| `enable_reranking`, `enable_query_expansion` | Toggle sub-features | Same | Always-on when beneficial |
| `enable_canonical_source_selection` | Toggle canonical pass | Canonical should be automatic | Authority from understanding layer |
| `enable_news_deprioritization_for_overview_queries` | News pages rank high on broad queries | Missing concept-level overview detection | Coverage + purpose from SI |
| `enable_broad_question_mode` | Inject overview pages | Broad queries fail without injection | Concept gap → evidence routing |

### 4.2 Dead / legacy settings (remove from API when safe)

| Setting | Status |
|---------|--------|
| `document_priorities_json` | DB column only — **no runtime consumer** |
| `scoring_weights_json` | DB column only — **no runtime consumer** |
| `intent_profiles_json` | DB column only — **no runtime consumer** |
| `enable_document_type_boosting` | Deprecated — ignored |
| `enable_about_page_boost` | Deprecated — ignored |

### 4.3 Knowledge Profile (largest config surface)

| Config | Why it exists | Should be |
|--------|---------------|-----------|
| Industry presets (`bank_financial`, …) | Bootstrap rules for verticals | **Removed** — auto from content |
| `document_type_rules` | URL→type classification | Emergent purpose from SI |
| `source_priority_rules` | Intent→boost doc types | Understanding-based evidence routing |
| `content_hint_rules` | Keyword→hint labels | Semantic tags from SI |
| `important_topics` + aliases | Manual topic taxonomy | Discovered concepts |
| `overview_query_patterns` | Define broad questions | Query cluster detection |
| `query_expansion_rules` | Manual synonym expansion | Concept alias index |
| Full JSON editor | Rule programming escape hatch | Read-only understanding view |

### 4.4 Source Intelligence ops (acceptable temporarily)

| Setting | Verdict |
|---------|---------|
| `enable_source_intelligence`, `enable_llm_source_intelligence` | Should become always-on; flag is transitional |
| Worker counts, batch sizes | Ops tuning — OK hidden in advanced ops, not "intelligence" |
| `source_intelligence_importance_threshold` | Patches ranking — replace with evidence quality |

### 4.5 Dashboard-specific

| UI surface | Path | Verdict |
|------------|------|---------|
| Knowledge Profile editor | `KnowledgeProfilePage.tsx` | **Legacy — largest RFC violation** |
| Industry preset loader | Same | **Remove** |
| Metadata boosts | `SettingsAdvancedSection.tsx` | **Remove** (title/heading boost) |
| RetrievalEnginePanel overrides | `RetrievalEnginePanel.tsx` | **Reduce** to mode preset only |
| Smart Search toggle | `SettingsPage.tsx` | **Remove** — intelligence always on |
| Chat diagnostics boost lists | `ChatRetrievalDiagnostics.tsx` | **Replace** with semantic reasoning trace |
| Analytics "expand knowledge profile" | `InsightsSections` i18n | **Replace** with autonomous remediation |

---

## 5. Subsystem-by-subsystem analysis

For each subsystem: current role, orientation, hardcode, config reliance, inference level, missing capability, replacement, incremental path.

---

### 5.1 Indexing pipeline

**Files:** `indexing_service.py`, `indexing_worker_service.py`, `crawler_service.py`, `reprocess_service.py`, `chunking_service.py`

| Question | Answer |
|----------|--------|
| What it does | Fetch URL → extract → classify document_type → chunk → embed → Qdrant; optional inline SI |
| Orientation | **Document-centric** |
| Hardcoded assumptions | Delegates classification to profile URL rules; reprocess by document_type filter |
| Manual configuration | Crawl depth, deny patterns, chunk size (ops-acceptable) |
| Page categories as primary logic | **Yes** — `document_type` on source and chunk payload |
| Infers understanding | Partial — triggers SI; does not write site-wide knowledge |
| Missing capability | Knowledge acquisition — "what did I learn?" per index event |
| Replace with | Index → SI → understanding delta → chunk as evidence artifact |
| Incremental | Hook understanding incremental updater post-SI; keep chunk pipeline unchanged |

---

### 5.2 Source Intelligence

**Files:** `source_intelligence_service.py`, `source_semantic_rules.py`, `source_intelligence_llm_service.py`, `source_intelligence_generation_service.py`, `source_intelligence_constants.py`, `source_intelligence_router.py`

| Question | Answer |
|----------|--------|
| What it does | Build per-page profile: structural flags + semantic JSON |
| Orientation | **Hybrid** — semantic JSON is knowledge-centric; structural layer is document-centric |
| Hardcoded assumptions | Full type/role taxonomy; importance/canonical from types; router intent frozensets |
| Manual configuration | LLM toggle, importance threshold, penalize campaigns |
| Page categories as primary logic | **Yes** when LLM off or content thin — rules fallback |
| Infers understanding | **Yes** when LLM on — main_topic, purpose, suitable_for |
| Missing capability | Cross-page merge; contradiction; site-wide concept index; open vocabulary |
| Replace with | **Knowledge Intelligence** — extract concepts, facts, relationships, uncertainty |
| Incremental | Strengthen LLM path; soften type→role dependency; feed understanding builder |

---

### 5.3 Knowledge Profile generation

**Files:** `knowledge_profile_generation/*`, `knowledge_profile_generator_service.py`

| Question | Answer |
|----------|--------|
| What it does | Analyze indexed pages → generate profile rules, topics, preview "graph" |
| Orientation | **Document-centric + retrieval-tuning** |
| Hardcoded assumptions | Bank entity regex, industry preset detection, URL category patterns |
| Manual configuration | Output requires admin apply; presets seed generation |
| Page categories as primary logic | **Yes** — structure analyzer, page-as-node graph |
| Infers understanding | Partial — topic discovery clusters pages, not concepts |
| Missing capability | Output should be understanding coverage report, not boost rules |
| Replace with | Continuous learning pipeline → Knowledge Memory snapshot |
| Incremental | Repurpose wizard as read-only understanding preview; stop emitting boost rules |

---

### 5.4 Knowledge Profile service

**Files:** `knowledge_profile_service.py`, `api/knowledge_profile.py`

| Question | Answer |
|----------|--------|
| What it does | Store/load profile; match intent & document_type; build boost tables |
| Orientation | **Retrieval-centric config hub** |
| Hardcoded assumptions | 7 industry presets, 14 doc-type URL rules, intent patterns |
| Manual configuration | **Entire subsystem is manual configuration** |
| Page categories as primary logic | **Yes** — core purpose |
| Infers understanding | No — applies rules |
| Missing capability | Site-wide understanding store |
| Replace with | Read-only view of Knowledge Memory; deprecate rule editing |
| Incremental | Mark presets deprecated; stop using boost tables in canonical selection |

---

### 5.5 Retrieval pipeline

**Files:** `retrieval_pipeline_service.py`, `retrieval_engine/*`

| Question | Answer |
|----------|--------|
| What it does | Orchestrate intent → expansion → document-first retrieval → canonical → context |
| Orientation | **Retrieval-centric** ( improving toward knowledge-centric scoring ) |
| Hardcoded assumptions | Broad inject score deltas; profile boost lists for canonical |
| Manual configuration | Retrieval profile, limits, feature flags |
| Page categories as primary logic | Partial — canonical uses doc types; scoring uses SI |
| Infers understanding | **Partial** — QueryUnderstanding + SemanticCompatibility |
| Missing capability | Reasoning orchestrator; evidence sufficiency; gap detection |
| Replace with | KnowledgeReasoningService wrapping retrieval as tool |
| Incremental | Add understanding resolver in shadow mode; do not rewrite pipeline yet |

---

### 5.6 Document scoring & reranking

**Files:** `document_scorer.py`, `semantic_compatibility.py`, `document_reranker.py`, `explanation_builder.py`

| Question | Answer |
|----------|--------|
| What it does | Blend lexical/dense with SI compatibility; rerank with purpose diversity |
| Orientation | **Knowledge-centric** (best subsystem alignment) |
| Hardcoded assumptions | Fixed internal blend weights |
| Manual configuration | Minimal — profile limits only |
| Page categories as primary logic | **No** in scorer — uses SI semantic fields |
| Infers understanding | **Yes** — purpose, suitable_for, evidence matching |
| Missing capability | Graph/memory signal; evidence independence; contradiction |
| Replace with | Add understanding_score; self-evaluation gate |
| Incremental | Extend scorer with understanding layer signal when Phase 2 ready |

---

### 5.7 Context builder & prompt builder

**Files:** `retrieval_engine/context_builder.py`, `context_builder_service.py`, `retrieval_engine/prompt_builder.py`

| Question | Answer |
|----------|--------|
| What it does | Assemble page bodies into context; intent-based prompt templates |
| Orientation | **Document-centric** assembly, **rule-driven** prompts |
| Hardcoded assumptions | `Type: {document_type}` in headers; intent frozensets → templates |
| Manual configuration | Context limits, system prompt override |
| Page categories as primary logic | **Yes** in context metadata |
| Infers understanding | No |
| Missing capability | Evidence bundles tied to concepts; reasoning-aware prompts |
| Replace with | Concept-grounded context blocks; prompt from resolved knowledge need |
| Incremental | Add concept labels alongside URLs; keep page bodies temporarily |

---

### 5.8 RAG / chat pipeline

**Files:** `rag_service.py`, `rag_streaming.py`, `chat_response_builder.py`, `llm_generation_service.py`

| Question | Answer |
|----------|--------|
| What it does | Cache → retrieve → LLM → polish → validate → response |
| Orientation | **Retrieval-centric** |
| Hardcoded assumptions | Intent-based prompt selection; fast-mode top_k |
| Manual configuration | System prompt, temperature, cache TTLs, polish |
| Page categories as primary logic | Indirect via retrieval |
| Infers understanding | No at orchestration level |
| Missing capability | Reasoning-first entry; self-evaluation; uncertainty responses |
| Replace with | Query → KnowledgeReasoning → evidence → LLM |
| Incremental | Wrap existing pipeline in reasoning shell (Phase 4) |

---

### 5.9 Canonical source service

**Files:** `canonical_source_service.py`

| Question | Answer |
|----------|--------|
| What it does | Reorder/limit context by profile doc-type boost lists |
| Orientation | **Document-centric + config-driven** |
| Hardcoded assumptions | Preferred/deprioritized document_type lists |
| Manual configuration | Profile rules + news deprioritization flag |
| Page categories as primary logic | **Yes** |
| Infers understanding | No |
| Missing capability | Canonical = highest-authority evidence for concept |
| Replace with | Understanding layer authority ranking |
| Incremental | Log when deprecated rules would fire; parallel understanding-based canonical |

---

### 5.10 Diagnostics

**Files:** `diagnostics_builder.py`, `retrieval_pipeline_service.RetrievalDiagnostics`, `chat_response_builder.DiagnosticsCollector`

| Question | Answer |
|----------|--------|
| What it does | Expose scores, candidate pages, boost lists, pipeline stages |
| Orientation | **Retrieval-centric / implementation-centric** |
| Hardcoded assumptions | Fields for boost_document_types, category_boosts (often empty) |
| Manual configuration | `enable_retrieval_debug` gate |
| Infers understanding | Partial — why_selected in reranker |
| Missing capability | RFC diagnostics: knowledge needed, evidence quality, gaps, certainty |
| Replace with | `understanding_trace` with semantic decisions |
| Incremental | Add parallel understanding diagnostics without removing existing (Phase 1) |

---

### 5.11 Analytics

**Files:** `analytics_service.py`, `analytics_aggregation_service.py`, dashboard analytics components

| Question | Answer |
|----------|--------|
| What it does | Trace aggregation: intents, topics, fallback rates, chunk scores |
| Orientation | **Operational**, lightly intent-aware |
| Hardcoded assumptions | Intent slug labels; doc_type in source analytics |
| Manual configuration | Recommendations point to manual profile expansion |
| Page categories as primary logic | Partial in source unused-pages view |
| Infers understanding | **No** — no coverage/contradiction/SI completeness |
| Missing capability | Knowledge health: concept coverage, learning rate, evidence quality |
| Replace with | Understanding dashboard; autonomous remediation suggestions |
| Incremental | Add understanding coverage metrics alongside existing KPIs |

---

### 5.12 Cache system

**Files:** `retrieval_cache_service.py`, `answer_cache_service.py`, `cache_namespace_service.py`

| Question | Answer |
|----------|--------|
| What it does | Cache chunk hits and answers keyed on query + tuning namespace |
| Orientation | **Retrieval-centric** |
| Hardcoded assumptions | Namespace hashes profile rules and boost settings |
| Manual configuration | TTLs, semantic cache threshold |
| Page categories as primary logic | No |
| Infers understanding | No — cache bypasses reasoning |
| Missing capability | Cache keyed on understanding version + evidence set |
| Replace with | Invalidate when knowledge memory changes; include confidence in cache entry |
| Incremental | Add understanding_version to namespace (Phase 5) |

---

### 5.13 Admin settings & dashboard

See Section 4 and dashboard audit. **Overall: retrieval-centric config shell** around a partially intelligent core.

---

### 5.14 Legacy hybrid retrieval

**Files:** `hybrid_retrieval_service.py`

| Question | Answer |
|----------|--------|
| Status | Test-only; doc-type boost removed from fuse |
| Action | Delete in Phase 1 after test migration |

---

## 6. Missing intelligence capabilities

Capabilities the architecture **needs** but does not yet have:

| Capability | Description | Unblocks |
|------------|-------------|----------|
| **Knowledge Memory** | Site-wide store of concepts, evidence links, confidence, coverage, contradictions | Reasoning, canonical, gap detection |
| **Knowledge acquisition** | Incremental "learned something" on each index event | Dynamic knowledge, obsolete detection |
| **Concept normalization** | Embedding-based merge/split of aliases | Dedup, cross-language |
| **Evidence authority inference** | Canonical from corroboration + quality, not document_type | Remove canonical rules |
| **Query reasoning** | Information need → required knowledge → sufficiency check | Replace retrieve-first |
| **Self-evaluation** | Enough evidence? Contradiction? Answer or admit uncertainty | Trust, explainability |
| **Open-vocabulary ontology** | Concepts emerge from content; no fixed purpose enums | Remove GENERIC_* frozensets |
| **Autonomous remediation** | System fixes gaps (re-embed, flag content) without admin | Remove analytics→settings loop |
| **Understanding-versioned cache** | Cache invalidates on knowledge change | Safe caching with reasoning |
| **Cross-source relationship inference** | Related concepts, supporting/contradicting evidence | Multi-source answers |

---

## 7. Proposed Knowledge OS architecture

### Target mental model

```
Website (observations)
  ↓
Knowledge Acquisition (per page: what did I learn?)
  ↓
Knowledge Memory (concepts, evidence, confidence, gaps)
  ↓
Knowledge Reasoning (query → need → evidence → sufficiency)
  ↓
Evidence Assembly (retrieval as tool)
  ↓
LLM + Self-evaluation
  ↓
Interfaces: Chat | Search | Analytics
```

### Core modules (new / evolved)

| Module | Role | Evolves from |
|--------|------|--------------|
| `KnowledgeAcquisition` | SI → concept deltas | Indexing + SI generation |
| `KnowledgeMemory` | Persistent understanding store | New (+ `SEMANTIC_UNDERSTANDING_MVP`) |
| `KnowledgeIntelligence` | Extract concepts, facts, relationships, uncertainty | Source Intelligence |
| `KnowledgeReasoning` | Orchestrate query understanding | New wrapper over retrieval |
| `EvidenceAssembly` | Retrieve + rank evidence | DocumentFirstRetrievalPipeline |
| `SelfEvaluation` | Confidence, gaps, uncertainty | New |
| `Explainability` | Semantic decision traces | ExplanationBuilder |

### Stable interfaces (representation-agnostic)

```
KnowledgeMemory.resolve(query_need) → concepts
KnowledgeMemory.evidence_for(concept) → sources
KnowledgeMemory.authority(concept) → canonical source
KnowledgeMemory.gaps(query_need) → missing knowledge
```

Graph, index, embeddings — **pluggable behind this interface**.

### What stays (as evidence layer)

- Qdrant chunk index (evidence lookup tool)
- `Source` / `Chunk` storage (observation artifacts)
- LLM generation infrastructure
- Crawl/index ops settings

### What shrinks

- Knowledge Profile rule editor → read-only understanding view
- Industry presets → deleted
- Boost/threshold admin settings → internal/automatic
- Intent frozensets → open vocabulary clusters

---

## 8. Migration roadmap

Incremental, production-safe. Aligns with RFC-0001 phased plan, reorganized per review request.

### Phase 1 — Cleanup and visibility (2–3 weeks)

**Goal:** Stop debt; make legacy visible; no behavior regression.

| Action | Risk |
|--------|------|
| Document deprecated paths (boost tables, presets, dead JSON columns) | None |
| Mark Knowledge Profile editor as legacy in UI copy | None |
| Add `understanding_trace` placeholder in debug diagnostics | Low |
| Migrate/remove hybrid retrieval tests | Low |
| Audit log when canonical would use doc-type rules | None |
| Produce understanding coverage report from existing SI (read-only script/API) | None |

**Exit criteria:** Team knows what is legacy vs production intelligence; no new config added.

---

### Phase 2 — Knowledge Intelligence layer (4–6 weeks)

**Goal:** Upgrade Source Intelligence toward Knowledge Intelligence; reduce type-taxonomy dependency.

| Action | Risk |
|--------|------|
| Strengthen LLM SI as default path | Medium — cost/latency |
| Soften rules fallback (open vocabulary purposes) | Medium — quality on thin pages |
| Extract concepts/facts/relationships/uncertainty into SI schema | Low |
| Stop using document_type as primary input to canonical/importance (parallel path) | Medium |
| Repurpose profile generation to emit understanding preview, not boost rules | Low |

**Exit criteria:** SI output includes concept-level fields; canonical has understanding-based alternative in shadow mode.

---

### Phase 3 — Knowledge Memory (4–6 weeks)

**Goal:** Persistent site-wide semantic memory (`SEMANTIC_UNDERSTANDING_MVP`).

| Action | Risk |
|--------|------|
| `understanding_snapshots`, `understanding_concepts`, `understanding_evidence` tables | Low |
| Understanding Builder aggregates SI after batch | Medium |
| Incremental updater on single-source index | Medium |
| `GET /api/understanding/summary` + dashboard read-only panel | None |

**Exit criteria:** System answers "what concepts exist?" and "which sources explain X?"; versioned with `knowledge_version`.

---

### Phase 4 — Reasoning layer (4–6 weeks)

**Goal:** Reason before retrieve; retrieval as tool.

| Action | Risk |
|--------|------|
| `KnowledgeReasoningService` wraps chat entry | Medium |
| Understanding Resolver + Evidence Finder (assist mode) | Medium |
| Self-evaluation: insufficient evidence → uncertainty response | Medium |
| Diagnostics → semantic decisions (RFC format) | Low |
| Context/prompt builders consume resolved knowledge need | Medium |

**Exit criteria:** Chat path goes through reasoning shell; flag-gated assist mode shows measurable lift.

---

### Phase 5 — Autonomous optimization (ongoing)

**Goal:** Remove manual settings and domain rules.

| Action | Risk |
|--------|------|
| Deprecate industry presets API | Medium — sites using bank preset |
| Remove boost settings from API/UI | Medium |
| Understanding-versioned cache | Medium — hit rate drop |
| Delete doc-type canonical rules | High — requires Phase 3–4 live |
| Analytics → autonomous remediation | Low |
| Continuous concept merge/split/obsolete detection | Medium |

**Exit criteria:** New unknown site indexes with URL only; admin cannot tune retrieval ranking.

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Quality regression when removing presets/boosts | Phase 3–4 must be live first; shadow mode eval |
| Two intelligence models confuse team | Phase 1 visibility; delete dead boost path |
| LLM SI cost/latency | Cache, batch, rules only as uncertainty fallback |
| Over-building graph before proving need | Concept index first; graph only if benchmarks win |
| Big-bang rewrite temptation | Strict incremental phases; feature flags |
| Bank preset users depend on boosts | Migration logging; offline eval on generic fixtures |
| Cache stale after understanding changes | understanding_version in namespace |
| Thin content sites fail open-vocabulary | Represent uncertainty; don't force classification |

---

## 10. Tests required

### Phase 1
- `test_no_production_hybrid_retrieval`
- `test_boost_tables_not_used_in_document_scorer`
- `test_deprecated_settings_not_in_api_response` (optional)

### Phase 2
- `test_si_extracts_concepts_without_document_type`
- `test_rules_fallback_admits_uncertainty`
- `test_no_bank_patterns_in_knowledge_intelligence_path`

### Phase 3
- `test_understanding_builder_from_si`
- `test_understanding_incremental_idempotent`
- `test_understanding_version_invalidation`

### Phase 4
- `test_reasoning_insufficient_evidence_uncertainty`
- `test_understanding_assist_improves_broad_queries`
- `test_diagnostics_semantic_not_scores`

### Phase 5
- `test_unknown_site_fixture_zero_admin_config`
- `test_no_industry_preset_in_production_path`
- `test_cache_stale_on_understanding_bump`

**Fixtures:** generic corporate + documentation sites only — not bank-specific regression suites as primary gate.

---

## 11. Files likely to change (by phase)

### Phase 1 (documentation, markers, tests)
- `docs/*` (this report, deprecation notices)
- `hybrid_retrieval_service.py` (test migration)
- `KnowledgeProfilePage.tsx` (legacy banner)
- `ChatRetrievalDiagnostics.tsx` (parallel trace field)

### Phase 2
- `source_intelligence_service.py`, `source_semantic_rules.py`
- `source_intelligence_llm_service.py`
- `schemas/source_intelligence.py`
- `knowledge_profile_generation/*` (reduce bank patterns)
- `source_intelligence_constants.py` (gradual deprecation)

### Phase 3
- `backend/app/services/knowledge_understanding/*` (new)
- `backend/app/models/understanding*.py` (new)
- `source_intelligence_generation_service.py` (rebuild hook)
- `api/understanding.py` (new)
- `dashboard` understanding coverage panel

### Phase 4
- `knowledge_reasoning/*` (new)
- `rag_service.py`, `rag_streaming.py`
- `retrieval_pipeline_service.py`
- `document_scorer.py`
- `retrieval_engine/prompt_builder.py`, `context_builder.py`
- `chat_response_builder.py`

### Phase 5
- `knowledge_profile_service.py`, `api/knowledge_profile.py`
- `canonical_source_service.py`
- `models/settings.py`, `api/settings.py`
- `cache_namespace_service.py`
- `SettingsAdvancedSection.tsx`, `KnowledgeProfilePage.tsx`
- `analytics_service.py`, analytics dashboard components

---

## 12. What NOT to implement yet

Do **not** start these until prior phases complete:

| Do not implement | Wait for |
|------------------|----------|
| Neo4j / external graph database | Phase 3 benchmarks prove multi-hop need |
| Full rewrite of RAG/chat | Phase 4 reasoning shell |
| Removing all document_type fields | Phase 2–3 authority inference live |
| Deleting Knowledge Profile API | Phase 3 understanding store + Phase 5 migration |
| New boost/penalty settings | Never |
| New industry presets or page categories | Never |
| Graph visualization admin editor | Never (read-only coverage only) |
| Cross-site / enterprise multi-tenant memory | Phase 3 stable single-site |
| Autonomous agents / tool calling | Phase 4–5 stable reasoning |
| Temporal reasoning | Phase 3 versioning foundation |
| Replacing Qdrant with new vector DB | Not required for Knowledge OS |
| LLM-on-every-query graph traversal | Evidence finder with bounded hops first |

### Do not implement now (Phase 1 scope creep)
- Knowledge Memory tables (that's Phase 3)
- Reasoning service wrapper (Phase 4)
- Removing presets from API (Phase 5)

---

## Decision: recommended next implementation step

**Start Phase 1 only:**

1. Publish this review and deprecation list
2. Add legacy markers to Knowledge Profile UI
3. Confirm `build_boost_tables()` / `category_boost()` unused in production (grep + test)
4. Read-only understanding summary from aggregated SI (no new tables yet — proves value)
5. Plan Phase 2 SI schema extensions

This is the lowest-risk step that increases visibility without changing chat behavior or adding technical debt.

---

## Related documents

| Document | Role |
|----------|------|
| `docs/RFC-0001-KNOWLEDGE-OS-CORE.md` | Canonical RFC |
| `docs/KNOWLEDGE_INTELLIGENCE_ENGINE.md` | Vision |
| `docs/MIGRATION_ROADMAP_KNOWLEDGE_OS.md` | Detailed phase deliverables |
| `docs/SEMANTIC_UNDERSTANDING_MVP.md` | Phase 3 build spec |
| `docs/ENGINEERING_MANIFEST.md` | Engineering principles |
