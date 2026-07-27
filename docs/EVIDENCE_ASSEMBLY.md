# Evidence Assembly (Release 0.6 — Step 040)

**RFC-100 Step 040** — introduce a **stateless** Evidence Assembly seam by wrapping
`DocumentFirstRetrievalPipeline` (DFP). Ownership and migration boundary only —
no retrieval or answer behavior changes.

## Why it exists

Release 0.6 continues extracting responsibilities from the legacy RAG stack.
Step 039 created `ReasoningService`. Step 040 creates **Evidence Assembly** as
the tool that gathers observation evidence on demand — without making retrieval
the architecture center.

## What it owns now

| Owns (contract) | Step 040 reality |
|-----------------|------------------|
| Typed assemble request | ✅ `EvidenceAssemblyRequest` |
| Single DFP invocation | ✅ `EvidenceAssemblyService.assemble` |
| Retrieval artifacts | ✅ reuses `DocumentRetrievalResult` (no duplicate result DTO) |
| Path diagnostics | ✅ `evidence_assembly_path=evidence_assembly` |

## What it does **not** own (and must not grow into)

- Query intent / QueryUnderstanding
- Evidence sufficiency or speech acts (Reasoning)
- Cognitive ranking policy as product mission
- Canonical-source / broad-query policy (still RPS)
- `RetrievalContextBuilder` / `prompt_text` (context prose → Language later)
- Prompt construction, LLM, polish, citations
- Answer / retrieval caches
- Epistemic Memory reads or writes

## Operational legacy ranking (explicit)

DFP still scores and reranks documents. Step 040 treats that ranking as
**operational legacy inside the retrieval tool**, not as Evidence Assembly’s
cognitive mission. Cognitive sufficiency and ranking ownership remain future
Reasoning work — not by stuffing more into this facade.

## What remains elsewhere

| Component | Owner after 040 |
|-----------|-----------------|
| Intent, expansion, broad inject, canonical, bilingual dedupe, context build | `RetrievalPipelineService` |
| Caches, prompts, LLM, polish, sources, finalize | `RagService` |
| Speech act / sufficiency contract | `ReasoningService` (still mostly passthrough) |
| Sensory indexes (Qdrant / lexical) | DFP retrievers (under EA when flag ON) |

## Call path

| Flags | DFP stage |
|-------|-----------|
| EA OFF | RPS → **DFP** |
| EA ON (Reasoning OFF) | RPS → **EvidenceAssemblyService** → DFP |
| Both ON (Step 041) | Reasoning orders RPS adapters; `assemble_evidence` → **EA** → DFP once |

Reasoning does not bypass RPS into EA as a God path — it only orders legacy adapters.

## What RPS still owns (legacy, intentional)

After Step 041, RPS remains the home for deferred adapters:

- query expansion, broad inject, canonical selection, bilingual dedupe
- `RetrievalContextBuilder` / `prompt_text` packing (Language later)
- diagnostics aggregation

These are **not** final ownership — documented debt for later steps.

## Statelessness

`EvidenceAssemblyService` holds only session/settings/embedding/qdrant deps and a
DFP instance used as a delegate. It does not cache hits, documents, or answers
across calls.

## Why it does not use Epistemic Memory yet

Memory is still shadow substrate. Memory-assisted evidence is Release 0.7
(Step 047+). Consuming claims/tensions here would change selection prematurely.

## Feature flag

| Flag | Default | Effect |
|------|---------|--------|
| `EVIDENCE_ASSEMBLY_ENABLED` | **false** | OFF: RPS constructs DFP directly (no EA on hot path). ON: RPS routes DFP stage through EA passthrough |

## Migration confidence (Step 042)

Gate suite validates all **8** Executive × Reasoning × EA combinations.
See [MIGRATION_CONFIDENCE_REPORT.md](MIGRATION_CONFIDENCE_REPORT.md).

## Performance (Step 040)

| Concern | Impact |
|---------|--------|
| Dispatch overhead | One extra Python call + thin request object when flag ON |
| Object allocation | One `EvidenceAssemblyRequest` per DFP stage when ON |
| Context copying | None beyond existing DFP/RPS handling |
| Additional retrieval | **Zero** — DFP runs exactly once |
| Additional LLM | **Zero** |
| Token impact | **None** |

## Migration boundaries (later)

| Step | Intent |
|------|--------|
| **041** | Thin RPS coordinator / Reasoning primary wiring |
| **042** | Golden suite gate with migration flags ON |
| **047** | Memory-assisted evidence (not this package’s growth into Reasoning) |

## Reality check (Step 040)

| Question | Answer |
|----------|--------|
| Thinner than RPS? | **Yes** — facade only |
| Retrieval once? | **Yes** — single DFP `run` |
| Reasoning leak? | **No** |
| Language leak? | **No** — no prompt/LLM; context builder stays in RPS |
| Memory leak? | **No** |
| Duplicate DFP result DTO? | **No** — reuses `DocumentRetrievalResult` |
| Flag OFF legacy? | **Yes** |
| Flag ON parity? | **Yes** — marker additive only |
