# Golden Query Suite

RFC-100 migration safety net. These queries test **architectural invariants**, not exact answer text or legacy retrieval quirks.

## Generic profile only (Step 056)

| Rule | Detail |
|------|--------|
| Required | `queries.json` must set `"fixture_profile": "generic_corporate"` |
| Loader | `parity_runner.load_golden_smoke()` **fails closed** if the field is missing, null, empty, or any other value |
| Schema | `test_golden_queries_schema.py` also asserts `generic_corporate` (defense in depth) |
| Scope | CI / golden tests only — production Knowledge Profiles are unaffected |
| Mocked parity | Unit golden parity builds a fixture `RagResult`; it does **not** exercise a live Knowledge Profile or apply industry `PRESETS` |
| Outside golden | Non-golden unit tests may still use industry `PRESETS` (`bank_financial`, `ecommerce`, etc.) |

## Files

| File | Purpose |
|------|---------|
| `queries.json` | Smoke suite (**30 queries**, Release 0.2) for CI |
| `parity_runner.py` | Loader + fixture `RagResult` + invariant checks |
| `README.md` | This guide |

`tests/test_golden_chat_parity.py` loads this file via `load_golden_smoke()` and runs parity checks against a **generic corporate fixture site**.

## CI smoke gate

| Mode | Requirements | What runs |
|------|--------------|-----------|
| **Unit (default PR CI)** | None | `test_golden_chat_parity.py` with mocked `RagService` / `ExecutiveService` |
| **HTTP integration (optional)** | `POSTGRES_TEST_URL` + `GOLDEN_CHAT_LIVE=1` | `/api/chat` boundary with mocks — still no live LLM |
| **Live ops shadow** | Deployed fixture site + LLM | Nightly / release verification |

Run unit golden smoke:

```bash
cd backend && .venv/bin/pytest tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -v -m unit
```

Enable optional HTTP integration:

```bash
export POSTGRES_TEST_URL=postgresql+psycopg://...
export GOLDEN_CHAT_LIVE=1
pytest tests/test_golden_chat_parity.py -m integration
```

## Design principles

1. **Generic fixture only** — `fixture_profile` must be `generic_corporate`; queries and URL patterns must work on generic corporate sites (e.g. `https://example.com`), not bank- or customer-specific content. The loader fails closed on any other profile.
2. **Structural expectations** — response shape, evidence linkage, diagnostics presence, forbidden anti-patterns.
3. **No exact answer text** — answers evolve; invariants do not.
4. **No brittle scores** — do not assert retrieval scores, boost values, or document-type ordering.
5. **No legacy locks** — do not encode document_type boosts or hybrid retrieval behavior as golden law.

## Query categories (smoke suite — 30 queries)

| Category | Count | Intent (typical) |
|----------|-------|------------------|
| `organization_overview` | 3 | `entity_overview` |
| `list_enumeration` | 3 | `category_overview` |
| `specific_fact` | 3 | `specific_fact` |
| `contact_support` | 3 | `contacts_query` |
| `pricing_rates` | 3 | `specific_fact` / `topic_overview` |
| `process_how_to` | 3 | `faq_like` / `topic_overview` |
| `policy_legal` | 3 | `specific_fact` / `faq_like` |
| `comparison` | 3 | `topic_overview` / `category_overview` |
| `negative_absent` | 3 | `unknown` |
| `ambiguity_clarification` | 3 | `unknown` |

## Golden item schema

Each entry in `queries.json` supports:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Stable identifier (`overview-001`, `pricing-002`, etc.) |
| `category` | yes | One of the categories above |
| `query` | yes | User message sent to `/api/chat` |
| `expected_intent` | yes | Primary intent from `QueryIntentService` |
| `expected_intent_alternatives` | no | Acceptable alternates (intent classification is heuristic) |
| `expected_source_patterns` | no | URL substrings; at least one source should match when `used_context` is true |
| `forbidden_source_patterns` | no | Sources must not match these (use sparingly) |
| `expect_used_context` | no | `true`, `false`, or `null` (don't assert) |
| `required_response_fields` | yes | Top-level JSON keys that must exist in `ChatResponse` |
| `required_diagnostics_keys` | yes | Keys present when `debug=true` (parity runner) |
| `forbidden_behaviors` | yes | See vocabulary in `queries.json` |

## Forbidden behavior vocabulary

Defined in `queries.json` → `forbidden_behavior_vocabulary`. The parity runner implements checks for each token. Add new tokens only when they express **platform invariants**, not accidental behavior.

Examples:

- `empty_sources_when_used_context_true` — evidence discipline
- `invented_enumeration_without_evidence` — no confident lists without grounding
- `sources_with_empty_url` — citation integrity

Do **not** add tokens that freeze implementation details (e.g. `must_use_about_page_document_type`).

## How to add a golden query

Use this checklist when extending the smoke suite (keep CI fast — prefer depth over duplication).

1. **Pick a category** — prefer one with fewer than three queries, or add a new edge case within an existing category.
2. **Assign a stable `id`** — `{category-prefix}-{nnn}` (e.g. `pricing-004`, `process-004`). Never reuse ids.
3. **Write a generic query** — no customer names, no industry presets, no bank-specific wording.
4. **Set intent expectations** — `expected_intent` plus `expected_intent_alternatives` from `QueryIntentService` vocabulary only.
5. **Source patterns** — URL **substrings** (`/pricing`, `support`), not full deployment URLs.
6. **Structural fields** — list `required_response_fields` from `ChatResponse` schema; keep diagnostics keys minimal (`query_intent`, `timing`, optional `metadata`).
7. **Forbidden behaviors** — pick from the vocabulary; propose new tokens in a PR with justification.
8. **Fixture alignment** — if you add a new `category`, extend `build_fixture_rag_result()` in `parity_runner.py` with a generic answer/title (no scores, no document types).
9. **Validate locally**:

   ```bash
   cd backend
   .venv/bin/pytest tests/test_golden_queries_schema.py tests/test_golden_chat_parity.py -v -m unit
   ```

10. **Update this README** — category table counts if you change coverage shape.

### Naming conventions

| Prefix | Category |
|--------|----------|
| `overview-` | `organization_overview` |
| `list-` | `list_enumeration` |
| `fact-` | `specific_fact` |
| `contact-` | `contact_support` |
| `pricing-` | `pricing_rates` |
| `process-` | `process_how_to` |
| `policy-` | `policy_legal` |
| `comparison-` | `comparison` |
| `negative-` | `negative_absent` |
| `ambiguity-` | `ambiguity_clarification` |

### When to use `expect_used_context`

| Value | Use when |
|-------|----------|
| `true` | Fixture should ground with at least one source |
| `false` | Refusal, clarification, or absent-info responses |
| `null` | Either grounded or honest fallback is acceptable |

### Optional per-query flags (future)

The schema may gain optional fields without breaking smoke:

```json
{
  "debug": true,
  "bypass_cache": true,
  "feature_flags": { "knowledge_os_executive_enabled": true }
}
```

Document new fields here before implementing runner support.

## Fixture site requirements

Golden parity tests expect an indexed fixture with pages matching generic patterns:

- `/about`, `/company`, or `about-us` — overview
- `/products`, `/services`, `/solutions` — enumeration
- `/pricing`, `/rates` — pricing
- `/help`, `/how-to`, `/onboarding` — process
- `/terms`, `/privacy`, `/legal` — policy
- `/contact`, `contact-us`, `/support` — contact
- No dedicated page for negative or ambiguity queries — honest refusal or clarification

Configure `fixture_site_pattern` in `queries.json` to match the test deployment base URL.

## What golden tests must not do

- Assert exact answer strings
- Assert retrieval scores or rank order
- Require specific `document_type` values on sources
- Lock UKRSIBBANK or any customer-specific URLs
- Fail on acceptable intent alternates listed in `expected_intent_alternatives`

## Related documents

- `docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md` — Steps 005–006, 018, §7.2
- `docs/DEVELOPMENT_CHARTER.md` — default implementation process
- `docs/ENGINEERING_PRINCIPLES.md` — evidence before answers, truthfulness before confidence
