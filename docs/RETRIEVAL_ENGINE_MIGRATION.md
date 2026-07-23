# Retrieval Engine Migration Report

## Summary

The retrieval architecture was refactored from a **chunk-first hybrid pipeline** into a **document-first production RAG pipeline**. Chunk-level fusion and page diversity heuristics were replaced by explicit document aggregation, weighted document scoring, intent-aware reranking, and structured diagnostics.

---

## Old Architecture

```
Query → Intent → Query Expansion
  → HybridRetrievalService (dense + lexical chunk merge)
  → _fuse() chunk scoring (partially wired)
  → category tagging (+ ad-hoc boosts)
  → SourceIntelligenceRouter (post-hoc chunk boosts)
  → canonical selection
  → chunk dedupe
  → _select_diverse_pages() (chunk list, multiple chunks per document)
  → RetrievalContextBuilder
  → LLM
```

### Problems

| Issue | Root cause |
|-------|------------|
| `final_score` always 0 in diagnostics | Diagnostics read pre-scored chunks; page summaries aggregated without propagating scores |
| `metadata_boost` / `intent_boost` empty | Set on chunks but lost during page grouping and context flattening |
| `score_breakdown` null | `RetrievalRankingService` existed but was **never wired** |
| `why_selected` / `why_rejected` empty | Only populated in debug mode on rejected chunks, not on document candidates |
| Pipeline stages stuck `pending` | Frontend expected stages backend never emitted; no state machine |
| Blogs beat product pages | Chunk-level ranking; no configurable document priorities |
| Multiple chunks per document dominated | No document deduplication before ranking |

### Legacy modules (still present, reduced role)

- `HybridRetrievalService` — retained for backward-compatible tests; **bypassed** by live pipeline
- `RetrievalRankingService` — superseded by `DocumentScorer`
- `RetrievalPipelineService._select_diverse_pages()` — superseded by `DocumentReranker`
- `RetrievalPipelineService._apply_source_intelligence()` — SI now integrated in `DocumentScorer` via `SourceIntelligenceScorer`
- Duplicate method definitions in `retrieval_pipeline_service.py` — **removed**

---

## New Architecture

```
Query → Intent Detection
  → Query Expansion
  → HybridChunkRetriever (dense + lexical, chunk-level only)
  → DocumentAggregator (group by source_id, best chunk per document)
  → DocumentScorer (weighted: semantic, lexical, metadata, doc type, intent, SI, freshness)
  → DocumentReranker (limit, minimum score, diversity, explanations)
  → [optional] broad page injection, canonical ordering, bilingual dedupe
  → RetrievalContextBuilder (one document → context block; neighbour chunks optional)
  → LLM
```

### New modules

| Module | Responsibility |
|--------|----------------|
| `retrieval_engine/config.py` | Scoring weights, document priorities, intent profiles, retrieval profiles |
| `retrieval_engine/retrievers.py` | `EmbeddingRetriever`, `LexicalRetriever`, `HybridChunkRetriever` |
| `retrieval_engine/document_aggregator.py` | Chunk → document grouping |
| `retrieval_engine/document_scorer.py` | Unified weighted document scoring |
| `retrieval_engine/intent_scorer.py` | Configurable intent-aware boosts |
| `retrieval_engine/source_intelligence_scorer.py` | SI metadata integration |
| `retrieval_engine/document_reranker.py` | Document selection + `why_selected` / `why_rejected` |
| `retrieval_engine/diagnostics_builder.py` | Quality metrics + candidate summaries |
| `retrieval_engine/pipeline_state.py` | Deterministic stage state machine |
| `retrieval_engine/pipeline.py` | `DocumentFirstRetrievalPipeline` orchestrator |
| `retrieval_engine/retrieval_profiler.py` | Profile resolution (Fast / Balanced / High Precision / High Recall / Enterprise) |

---

## Scoring Pipeline

Configurable weights (default):

| Signal | Weight |
|--------|--------|
| Semantic similarity | 35% |
| Lexical score | 25% |
| Document type / metadata | 15% |
| Intent match | 10% |
| Source Intelligence | 10% |
| Freshness | 5% |

Every selected document exposes:

- `dense_score`, `lexical_score`, `metadata_boost`, `intent_boost`, `quality_boost`, `freshness_boost`, `final_score`, `confidence`
- `score_breakdown` (weighted components + raw scores)
- `why_selected`, `why_rejected`, `ranking_reason`

Document type priorities are configurable via `document_priorities_json` in Settings (defaults include `product_page +0.30`, `blog_page -0.10`, etc.).

Intent profiles are configurable via `intent_profiles_json`.

---

## Configuration (Settings)

New columns (migration `0010_document_first_retrieval`):

- `retrieval_profile` — `fast` | `balanced` | `high_precision` | `high_recall` | `enterprise`
- `document_priorities_json`
- `intent_profiles_json`
- `scoring_weights_json`
- `top_k_dense`, `top_k_lexical`, `rerank_limit`, `document_limit`, `minimum_retrieval_score`

---

## Diagnostics

New payload fields in `RetrievalDiagnostics`:

- `quality_metrics` — documents found, after dedup, after rerank, sent to LLM, averages, filters
- `retrieval_pipeline_stages` — per-stage status (pending / running / completed / failed / skipped)
- `score_breakdowns` — per-document weighted breakdown
- `rejected_candidates` — documents with `why_rejected`

`DiagnosticsCollector` updated to prevent stale `running` stages and merge retrieval sub-stages.

---

## Tests

New: `tests/test_document_first_retrieval.py`

- Document aggregation
- Document scoring (final_score, breakdown)
- Intent scoring
- Reranker explanations
- Diagnostics quality metrics
- Pipeline state machine
- Config loading

Existing tests continue to pass (`test_retrieval_engine`, `test_boilerplate_retrieval`, `test_chat_response_builder`, pipeline v2, broad query, SI pipeline).

---

## Remaining Technical Debt

1. **`HybridRetrievalService`** — still used by legacy tests; candidate for deprecation once tests migrate to `HybridChunkRetriever`.
2. **`RetrievalRankingService`** — orphaned; should be deleted or aliased to `DocumentScorer`.
3. **`RagService._retrieve_hits()`** — dead code with unused fallback second pass.
4. **`enable_reranking`** — now toggles `DocumentReranker`; profile limits still apply when disabled.
5. **Broad page injection** — still post-rerank; ideally converted to document candidates pre-rerank.
6. **Settings UI** — dashboard has no editor yet for `document_priorities_json`, `intent_profiles_json`, `scoring_weights_json`, `retrieval_profile`.
7. **Cross-encoder reranker** — rule-based reranking only; no ML rerank model.
8. **Lexical on SQLite** — FTS remains PostgreSQL-only.

---

## Deployment

Run migration:

```bash
cd backend && alembic upgrade head
```

Restart backend after deploy. Hard-refresh dashboard to see updated diagnostics fields.
