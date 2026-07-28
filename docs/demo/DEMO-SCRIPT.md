# Live demo script — Knowledge OS (honest)

**Audience:** product / client / engineering  
**Duration:** ~15–20 minutes  
**Do not enable migration flags or shadow write during the demo.**

## Preconditions

- App points at restored corpus (`ai_site_agent_recovery` or production after cutover)
- Backend healthy (`/api/health`)
- Admin login available
- Prefer dashboard language Ukrainian or English consistently

## Script

### 1. Overview (2 min)

Open **Overview**.

Say: “This is a Knowledge OS for website knowledge — indexing pages, understanding sources, and answering grounded questions.”

Show live cards: sources, chunks, health (Postgres / Qdrant / Ollama), Knowledge OS panel (release 0.5 accepted, 0.6 in progress, flags OFF).

### 2. Indexed corpus (1 min)

Point at source/chunk/vector counts from Overview (API-backed). Mention UKRSIBBANK corpus restored for this environment.

### 3. Sources (3 min)

Open **Sources**. Filter Ready. Open one real `ukrsibbank.com` page.

Show: indexed status, chunk count, Source Intelligence fields / panel if present.

Say: “Indexed text becomes chunks; Source Intelligence summarizes the page for operators — it does not yet drive chat through Epistemic Memory.”

### 4. Source Intelligence (1 min)

From Indexing or source detail, show SI status / last generated time. Coverage is partial (~2.2k of ~5k in recovery snapshot) — be honest.

### 5. Chat Test (4 min)

Open **Chat**. Ask a known factual question about the site (e.g. branches / products that exist in the index).

Show: one answer, sources with title + URL, timing if visible.

Open the **diagnostics / engineering drawer** only if asked — explain `reasoning_path` / flags are migration seams and currently OFF so the path is Rag → Retrieval → Ollama.

### 6. Knowledge OS seams (2 min)

On Overview or Settings → Migration flags:

- Executive / Reasoning / Evidence Assembly: **available behind flag**, currently OFF → same answers by design
- Speech-act Language: requires Reasoning + deployed Step 045
- Memory shadow write: OFF; Memory not used in chat

### 7. Epistemic Health (4 min)

Open **Diagnostics → Epistemic Health**.

Read the subtitle aloud (hypotheses, not confirmed errors; do not affect chat).

Show badges: Experimental, Diagnostic-only, Chat impact Not active, Shadow writes OFF.

Show **real** summary cards. If real open tensions = 0, say that clearly.

Switch provenance filter to **Test** only if you want to show fixture noise — explain these will be cleaned after approval, not production knowledge errors.

Expand one tension → Copy JSON for engineers. Emphasize wording: “Possible support deficit / Possible conflict.”

### 8. Maturity + architecture (2 min)

Scroll to capability maturity and architecture visual.

Active path: User → Chat → Rag → RetrievalPipeline → DocumentFirstRetrieval → Ollama → Answer.

Diagnostic path: SI → Epistemic Memory → Tension Surfacing → this page.

Memory dashed line: does **not** influence answers today.

### 9. Close (1 min)

Next milestone: Release 0.7 memory-assisted evidence (not built yet).  
Offer Q&A. Do not promise Maintenance / belief revision / auto conflict resolution.

## Anti-patterns (do not say)

- “Understanding shows how the website is understood”
- “These conflicts are bugs / false claims”
- “Memory already improves answers”
- “Release 0.6 is done”
- “Speech acts are live” (unless `/api/build` shows the flag supported **and** enabled)
