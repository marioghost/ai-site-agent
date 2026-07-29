# Post-0.8 Machine / Environment Migration — Architecture Review

**Status:** **Part 1 of 2 — complete. NOT approved. NOT executed.**  
**Scope of this part:** old-machine topology, measured facts, and derived requirements.  
**Part 2 (canonical blueprint):** [MACHINE-MIGRATION-MANIFEST.md](MACHINE-MIGRATION-MANIFEST.md) — resolves all 20 determinations, and supersedes the deferrals recorded below.  
**Date:** 2026-07-29  
**Base:** `main` @ `1c8c16e` (Release 0.8 operational deployment merged)  
**Entry gate:** [RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md) — deployment accepted 2026-07-29  
**Plan of record:** [POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md)

**Public operator entry point on every host:**

```bash
bash deploy/manage_deploy.sh <command>
```

Makefile targets (`make release-check`, …) are internal developer/CI validation helpers only.

> **Nothing in this document authorizes execution.** No PostgreSQL restore, Qdrant restore, Ollama
> migration, secrets transfer, DNS/host cutover, systemd change, nginx change, or production write
> may occur until this review is **complete and approved**. The old host remains the rollback
> target until new-machine acceptance is recorded.

---

## Why this part stops where it does

Twelve of the twenty required determinations depend on facts about the target machine that do not
exist anywhere in this repository or on the current host: its OS, its hardware, whether it becomes
the sole runtime host, and whether it has a GPU. Writing those sections from assumption would
produce a document that *reads* like a review while encoding invented topology — the precise
failure mode this program exists to prevent.

So Part 1 establishes the **measured** old-machine baseline and the **requirements that follow from
it**, and every new-machine determination is explicitly deferred with the input needed to close it.
Requirements derived here are durable regardless of what the target turns out to be.

All values below were measured read-only on 2026-07-29. No configuration was changed.

---

## 1. Exact old-machine topology

**DETERMINED.**

### Host

| Property | Measured value |
|----------|----------------|
| Hostname | `DESKTOP-I2KQV1N` |
| OS | **Ubuntu 24.04.4 LTS** (Noble Numbat), `VERSION_ID=24.04` |
| Kernel | `6.6.87.2-microsoft-standard-WSL2`, `x86_64` |
| Virtualization | **WSL2** on Windows (`WSL_DISTRO_NAME=Ubuntu`, `WSL_INTEROP` set) |
| Init | **systemd is PID 1**; `systemctl is-system-running` → **`running`** |
| CPU | Intel Core i9-9880H @ 2.30 GHz, **16 logical CPUs** |
| RAM | **7.7 GiB total** (2.3 GiB used, 5.4 GiB available), 2.0 GiB swap |
| Root filesystem | `/dev/sdd`, **ext4**, 1007 GB total, 23 GB used, **934 GB available (3 %)** |
| GPU | **No CUDA GPU exposed** — `nvidia-smi` absent; `/dev/dxg` present (WSL paravirt only) |
| Container runtime | **Docker not installed** |

`systemd` availability is worth stating plainly because the `health` readout is misleading about
it: see [DEBT-0.8-002](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md) in §2 of the deployment
report. All five service units are **enabled and active**.

### Service topology — single host, loopback-only except nginx

| Service | Version | Bind | Managed by | Runs as |
|---------|---------|------|-----------|---------|
| nginx | 1.24.0 (Ubuntu) | **`0.0.0.0:80`** | `nginx.service` (packaged) | root → `www-data` workers |
| Backend (FastAPI/uvicorn) | — | `127.0.0.1:8000` | `ai-agent-backend.service` | **`home:home`** |
| PostgreSQL | **16.14** (Ubuntu 16.14-0ubuntu0.24.04.1) | `127.0.0.1:5432` | `postgresql.service`, cluster `16/main` | `postgres` |
| Qdrant | **1.12.4** (commit `5b578c4f`) | `127.0.0.1:6333` HTTP, `127.0.0.1:6334` gRPC | `qdrant.service` | `qdrant:qdrant` |
| Ollama | **0.30.10** | `127.0.0.1:11434` | `ollama.service` | `ollama:ollama` |

**nginx on `0.0.0.0:80` is the only externally reachable port.** Everything else is loopback-bound,
which is the single most important property to preserve: the security model is "bind to loopback,
expose one reverse proxy," not "firewall the ports."

### Toolchains

| Tool | Version | Path | Migration note |
|------|---------|------|----------------|
| Python | **3.12.3** | `/usr/bin/python3` | backend venv also 3.12.3 |
| Node | **v20.20.2** | `/home/home/.nvm/versions/node/v20.20.2/bin/node` | **nvm, user-scoped** — see §12 hazard |
| npm | 10.8.2 | same nvm prefix | pinned in `deploy.local.conf` |
| psql / pg_dump / pg_restore | 16.14 | `/usr/bin` | client major must be ≥ server major |
| git | 2.43.0 | `/usr/bin/git` | |
| rsync | 3.2.7 | `/usr/bin/rsync` | used by `deploy full` sync stage |
| Qdrant binary | 1.12.4 | `/opt/qdrant/qdrant` | **not** on `PATH`, not packaged |

### Data inventory — what actually has to move

| Asset | Location | Size | Nature |
|-------|----------|------|--------|
| `ai_site_agent` (live DB) | Postgres cluster `16/main` | **103 MB** | authoritative relational state |
| `ai_site_agent_recovery` | same cluster | **107 MB** | **incident DB only** — see §6 |
| Qdrant storage | `/var/lib/qdrant/storage` | **143 MB** | vectors; rebuildable but expensive |
| Qdrant install | `/opt/qdrant` | 73 MB | binary + `config.yaml` |
| Ollama models | `/usr/share/ollama/.ollama/models` | **7.3 GB** | 3 models, re-pullable |
| `/opt` backend | `/opt/ai-site-agent/backend` | 366 MB | venv — **rebuild, do not copy** |
| `/opt` dashboard | `/opt/ai-site-agent/dashboard` | 209 MB | `node_modules` + `dist` — rebuild |
| Backups | `/opt/ai-site-agent/backups` | **809 MB**, 51 dumps | see §17 |
| Logs | `/opt/ai-site-agent/logs` | 624 KB, 89 files | operational history |
| Deploy manifests | `/opt/ai-site-agent/deployments` | 2 manifests | audit trail |
| Dev checkout | `/home/home/projects/ai-site-agent` | 608 MB (`.git` 13 MB) | **clean clone instead** |
| Cursor user data | `/home/home/.cursor` | 37 MB | see §9 |
| Cursor remote server | `/home/home/.cursor-server` | 738 MB | **regenerated — never copy** |

**Irreplaceable payload is small: ~250 MB** (`ai_site_agent` 103 MB + Qdrant 143 MB). Everything
else is either rebuildable from `origin/main`, re-pullable, or historical. This is the key sizing
fact for the cutover window — the transfer is minutes, not hours.

### Database detail

| Property | Value |
|----------|-------|
| Server version | 16.14 |
| Data directory | `/var/lib/postgresql/16/main` |
| Config | `/etc/postgresql/16/main/postgresql.conf` |
| Login roles | `ai_agent`, `postgres` |
| Extensions | **`plpgsql` only** — no `pgvector`, no `pg_trgm` |
| Alembic revision | `0019_legacy_doc_type_canonical_enabled` |
| Connection | `postgresql+psycopg://ai_agent:***@localhost:5432/ai_site_agent` |
| Largest tables | `chunks` 52 MB, `sources` 37 MB, `source_intelligence_llm_cache` 1.7 MB, `chat_messages` 840 kB |

The extension list being `plpgsql` only is a genuine simplification: **there is no extension
version-compatibility risk.** Vectors live in Qdrant, not in Postgres.

### Qdrant detail

```yaml
storage:
  storage_path: /var/lib/qdrant/storage
  snapshots_path: /var/lib/qdrant/snapshots
service:
  host: 127.0.0.1
  http_port: 6333
  grpc_port: 6334
```

| Collection | Points | Status | Segments | Vector config |
|------------|--------|--------|----------|---------------|
| `site_knowledge` | **18780** | `green` | 8 | size **1024**, distance **Cosine** |
| `site_knowledge_answer_cache` | **7** | `green` | 8 | size 1024, distance Cosine |

The 1024-dimension Cosine config must be reproduced exactly — it is tied to the `bge-m3` embedding
model. A dimension or distance mismatch would not fail loudly; it would silently degrade retrieval.
Server-side `snapshots_path` is already configured, so the native snapshot API is available and is
the correct transfer mechanism (§7).

### Ollama detail

| Model | Size | Parameters | Quantization | Role |
|-------|------|-----------|--------------|------|
| `qwen2.5:3b` | 1.93 GB | 3.1 B | Q4_K_M | **runtime LLM** (`DEFAULT_LLM_MODEL`, `OLLAMA_WARMUP_MODEL`) |
| `bge-m3:latest` | 1.16 GB | 566.70 M | **F16** | **embeddings — 1024-dim, pinned to Qdrant config** |
| `qwen2.5:7b` | 4.68 GB | 7.6 B | Q4_K_M | optional; GPU-appropriate, too slow on CPU |
| **Total** | **7.77 GB** | | | 3 models — **only 3.09 GB on the critical path** |

`qwen2.5:3b` is the configured runtime model, not the 7B: `.env` sets
`DEFAULT_LLM_MODEL=qwen2.5:3b` and `OLLAMA_WARMUP_MODEL=qwen2.5:3b`, migration
`0009_cpu_local_model_defaults` sets `llm_model='qwen2.5:3b'`, `docs/STAGING-SEED-SMOKE.md` requires
only `qwen2.5:3b` and `bge-m3` for smoke, and `deploy/OLLAMA.md` records that CPU-only `qwen2.5:7b`
takes 50 s+ to first token. Digests for all three are recorded in
[MACHINE-MIGRATION-MANIFEST.md](MACHINE-MIGRATION-MANIFEST.md) §1.

`bge-m3` is not interchangeable. Its 1024-dimension output is baked into both Qdrant collections
and into every stored vector, so it must be present on the new host **before** any retrieval.

---

## 2. Exact new-machine topology and OS

**DEFERRED — no data available.**

Cannot be determined from this repository or the current host. Required inputs: OS and version;
bare metal / VM / WSL2 / container; CPU, RAM, disk; GPU model and VRAM; whether systemd is
available as PID 1.

**Requirements this must satisfy, derived from §1** (these hold regardless of the answer):

| # | Requirement | Source |
|---|-------------|--------|
| R1 | PostgreSQL server major version **≥ 16** | dumps are from 16.14; `pg_restore` is not backward-compatible across majors |
| R2 | Qdrant **1.12.x** or a version with a documented 1.12 snapshot-restore path | snapshot format compatibility |
| R3 | Python **3.12.x** | `requirements.txt` pins are validated on 3.12.3 |
| R4 | Node **20.x** (v20.20.2 known-good) | dashboard build |
| R5 | ≥ 20 GB free disk for runtime, plus backup retention headroom | 7.3 GB models + 250 MB data + 575 MB `/opt` build artifacts + backups |
| R6 | ≥ 8 GB RAM; **more strongly recommended** | current host runs a 7.6 B model in 7.7 GiB — see §Risks |
| R7 | An init system able to express the §13 unit dependency graph | `ai-agent-backend` must start after Qdrant and Ollama |
| R8 | Ability to bind Postgres, Qdrant, and Ollama to loopback only | current security model |

---

## 3. Which machine becomes runtime host

**DEFERRED — policy decision, not a technical finding.**

Required input: does the new machine become the **sole** runtime host, or does the old host keep
serving during a parallel window?

The technical constraint is fixed regardless: **exactly one host may accept writes at any instant.**
The corpus, Epistemic Memory, and Qdrant have no merge or conflict-resolution mechanism, so two
hosts writing concurrently produces divergence that cannot be reconciled — only discarded. The
migration must therefore be a **write-freeze then cutover**, never a dual-write overlap.

Recorded options, for the Part 2 decision:

| Option | Dual-write risk | Rollback | Note |
|--------|----------------|----------|------|
| **A. Hard cutover** — freeze old, migrate, start new, old host read-only standby | **none** | repoint to old host | matches the "avoid dual-write ambiguity" constraint most directly |
| **B. Parallel run, new host read-only** | none if enforced | trivial | useful for validation; requires a real read-only guarantee, not a convention |
| **C. Parallel run, both writable** | **unacceptable** | corpus divergence | **must not be used** |

---

## 4. Whether PostgreSQL, Qdrant and Ollama move together

**PARTIALLY DETERMINED — the coupling is measured; the staging decision is deferred.**

| Pair | Coupling | Consequence |
|------|----------|-------------|
| Postgres ↔ Qdrant | **Tight** | `chunks` rows and `site_knowledge` points are the same knowledge at `knowledge_version=26`. A version skew between them is a silent retrieval-correctness bug, not an outage. |
| Qdrant ↔ Ollama (`bge-m3`) | **Tight** | stored vectors are `bge-m3` 1024-dim outputs; a different embedding model invalidates all 18780 points |
| Postgres ↔ Ollama (LLM) | **Loose** | `qwen2.5` models affect answer generation, not stored state |

**Derived requirement: PostgreSQL and Qdrant must move as one atomic unit**, from the same
write-frozen instant. Ollama may move independently — it holds no mutable state — but `bge-m3`
must be present before the first retrieval on the new host.

Deferred: whether the move is one window or staged, which depends on the §3 decision.

---

## 5. Downtime / write-freeze strategy

**PARTIALLY DETERMINED — mechanism identified; window size deferred.**

Required input: acceptable downtime window.

### Available freeze mechanism (measured, not yet chosen)

The write surface is narrow and already flag-gated, which makes a clean freeze achievable:

| Write path | How it is stopped | Verification |
|------------|-------------------|--------------|
| Indexing / crawl jobs | no job running — newest `index_jobs` id 46 finished 2026-07-28 06:32 | `index_job_status` in `health` |
| Chat writes (`chat_messages`, `answer_traces`) | stop `ai-agent-backend.service` | `systemctl is-active` |
| Epistemic Memory writes | already **off** — `memory_shadow_write_enabled=false` | `/api/build` `feature_flags` |
| Qdrant upserts | only reachable through the backend | backend stopped |

Because the backend is the **sole writer** to both Postgres and Qdrant, and it is a single systemd
unit bound to loopback, **stopping one unit freezes all writes.** No application-level read-only
mode is required.

### Sizing evidence

Irreplaceable payload is ~250 MB (§1). A `pg_dump` of `ai_site_agent` takes seconds — the Gate D
stage-1 backup on 2026-07-29 produced an 11.6 MB compressed dump as part of a deploy that completed
in **48 seconds end to end**. The dominant cost is Ollama's 7.3 GB, which can be pre-staged
**before** the freeze because models are immutable.

**Derived strategy:** pre-stage everything immutable (OS packages, clean `origin/main` clone,
Ollama models, Qdrant binary), then freeze, then move only the ~250 MB of mutable state. The freeze
window is bounded by dump + transfer + restore + verify, not by the total data volume.

---

## 6. PostgreSQL backup and restore method

**DETERMINED for backup. Restore method determined; execution deferred.**

### Backup — use the supported operator command

```bash
bash deploy/manage_deploy.sh backup db
```

This is the only sanctioned path and it is proven: three dumps taken during the Release 0.8
deployment were verified by SHA256 and `pg_restore --list`
([report §3](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md)). It writes custom-format dumps to
`/opt/ai-site-agent/backups/ai_site_agent.<timestamp>.dump`.

| Property | Value |
|----------|-------|
| Format | PostgreSQL **custom** (`pg_dump -Fc`) — `pg_restore`-compatible, selective, compressed |
| Typical size | ~11.6 MB compressed from 103 MB logical |
| Validation | `sha256sum` + `pg_restore --list` (expect 217 TOC entries, 19 `TABLE DATA`, `public.settings` present) |

### Restore requirements

| # | Requirement | Reason |
|---|-------------|--------|
| P1 | Target server major **≥ 16** | R1 |
| P2 | Create role `ai_agent` with the same name **before** restore | dumps carry `ai_agent` ownership |
| P3 | Create an empty `ai_site_agent` database owned by `ai_agent` | avoid restoring into a populated DB |
| P4 | Restore, then verify `alembic_version` = `0019_legacy_doc_type_canonical_enabled` | schema identity |
| P5 | Verify corpus counts: sources **5023**, chunks **17958**, claims **39**, observations **13**, evidence links **21** | baseline from report §10 |
| P6 | Verify `knowledge_version=26`, `memory_version=177` (settings row 1) | pairing with Qdrant |
| P7 | Verify all 11 flag columns **false** on both settings rows | report §8 |
| P8 | Do **not** run `alembic upgrade` as a substitute for restore | schema must arrive with its data |

### `ai_site_agent_recovery` — explicit decision required

This 107 MB database is an **incident artifact**, not part of the runtime. `.env` `DATABASE_URL`
points only at `ai_site_agent`; nothing in the application references the recovery DB.

**Recommendation: do not migrate it as a live database.** Preserve it as a dump in cold storage if
it still has forensic value, and record the decision explicitly. Silently carrying a second
database that resembles the live one onto a fresh host is how the wrong `DATABASE_URL` gets
configured later.

---

## 7. Qdrant snapshot and restore method

**DETERMINED for method; execution deferred.**

`snapshots_path: /var/lib/qdrant/snapshots` is already configured, so the **native snapshot API is
the correct mechanism**. A filesystem copy of `storage_path` is not equivalent: it is only safe
against a stopped Qdrant, and it captures segment state that may be mid-compaction.

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Snapshot **both** collections after the write freeze | snapshot files present in `snapshots_path` |
| 2 | Checksum each snapshot | SHA256 recorded alongside |
| 3 | Transfer over a secure channel | checksum re-verified on arrival |
| 4 | Restore on the new host | collection `status=green` |
| 5 | Verify point counts | `site_knowledge` = **18780**, `site_knowledge_answer_cache` = **7** |
| 6 | Verify vector config | size **1024**, distance **Cosine**, both collections |
| 7 | Verify pairing with Postgres | `knowledge_version=26` in settings, chunks = 17958 |

`site_knowledge_answer_cache` (7 points) is a **derived cache** and may legitimately be recreated
empty instead of restored. If it is recreated, it must use the identical 1024/Cosine config. State
the choice explicitly in Part 2 rather than leaving it to whoever runs the cutover.

**Forbidden as a "fix":** clearing or recreating `site_knowledge`. Re-embedding 18780 points is a
long, CPU-bound reindex on a host without GPU acceleration, and it changes retrieval results. The
plan of record already prohibits this ("do **not** clear Qdrant as a 'fix'").

---

## 8. Ollama model transfer versus re-pull

**DEFERRED on the transfer-vs-pull decision — it depends on new-host GPU and bandwidth. Constraints determined.**

Required inputs: new-host GPU model and VRAM; available bandwidth.

| Approach | Pros | Cons |
|----------|------|------|
| **Re-pull** (`ollama pull qwen2.5:7b qwen2.5:3b bge-m3`) | clean, no stale blobs, no permission fixups | 7.77 GB download; `:latest` **may resolve to a different digest** |
| **Copy** `/usr/share/ollama/.ollama/models` (7.3 GB) | byte-identical models, no network dependency | must fix `ollama:ollama` ownership; couples hosts' directory layouts |

**Critical constraint regardless of choice:** `bge-m3:latest` is a **floating tag**. If a re-pull
resolves to a newer `bge-m3` build whose embeddings differ, the 18780 restored vectors become
subtly inconsistent with newly embedded queries — a silent retrieval-quality regression, not an
error. Therefore:

| # | Requirement |
|---|-------------|
| O1 | Record the current `bge-m3` digest on the old host **before** migration |
| O2 | After migration, verify the new host's `bge-m3` digest **matches**; if it does not, prefer copying the model blob over accepting the newer build |
| O3 | Pin embedding-model identity in acceptance criteria, not just presence |
| O4 | `qwen2.5:3b` / `qwen2.5:7b` may be re-pulled freely — they affect generation, not stored vectors |

**Digests recorded (O1 satisfied)** — see
[MACHINE-MIGRATION-MANIFEST.md](MACHINE-MIGRATION-MANIFEST.md) §1: `bge-m3:latest` =
`7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`
(blob `sha256-daec91ffb5dd…3062c`, `bert.embedding_length=1024`), `qwen2.5:3b` =
`357c53fb659c…9e4b`, `qwen2.5:7b` = `845dbda0ea48…697e`.

Note on hardware: the current host has **no CUDA GPU** (`/dev/dxg` paravirt only), so today's
performance baseline is effectively CPU inference of a 7.6 B Q4_K_M model in 7.7 GiB RAM. A new host
with a real GPU would change performance characteristics substantially — which is good, but it means
**performance baselines from the old host are not a valid acceptance threshold** for the new one.

---

## 9. Cursor migration

**PARTIALLY DETERMINED — old-host inventory measured; new-host install steps deferred.**

| Item | Old-host state | Migration treatment |
|------|----------------|---------------------|
| Installation | Cursor desktop on Windows; WSL remote server at `/home/home/.cursor-server` (**738 MB**) | **Install fresh. Never copy `.cursor-server`** — it is a versioned remote-server payload keyed to a build hash and is regenerated on first connect |
| Settings | Cursor user data `/home/home/.cursor` (37 MB): `ide_state.json`, `plans`, `plugins`, `projects`, `skills-cursor` | selective — `ide_state.json` and `projects` are host-specific session state, not portable config |
| Extensions | in Cursor user data | reinstall from Cursor; do not copy binaries |
| `.cursor` rules | **`.cursor/rules/` is in git** — `release-engineering-workflow.mdc`, `knowledge-intelligence-manifest.mdc`, `knowledge-os-development-charter.mdc` (20 KB) | **arrives automatically with the clean clone — no action required** |
| MCP / connectors | **no `mcp.json`** at `~/.cursor/mcp.json` or `<repo>/.cursor/mcp.json` | nothing to migrate; if MCP is added later it is new configuration, not migration |
| Project instructions | **no `AGENTS.md`** in the repo | nothing to migrate |
| Terminal profiles | not separately configured on this host | nothing to migrate |
| Skills | `/home/home/.cursor/skills-cursor` (user-level) | re-provision at user level; not repository state |

The genuinely reassuring finding: **the repository-scoped agent configuration that matters is
version-controlled.** The three `.mdc` rule files — including the release-engineering workflow that
governs this whole program — come with the clone. The 775 MB of Cursor state on disk is
overwhelmingly regenerable cache, not configuration.

---

## 10. Secrets transfer method

**DETERMINED for inventory; channel deferred.**

Required input: chosen secure channel.

### Inventory — key names only; **no values were read or printed**

| File | Owner / mode | Keys |
|------|--------------|------|
| `/opt/ai-site-agent/.env` | `home:home` **600** | `APP_ENV`, `APP_HOST`, `APP_PORT`, **`DATABASE_URL`**, `OLLAMA_BASE_URL`, `OLLAMA_WARMUP_ENABLED`, `OLLAMA_WARMUP_MODEL`, `OLLAMA_KEEP_ALIVE`, `QDRANT_HOST`, `QDRANT_PORT`, `DEFAULT_LLM_MODEL`, `DEFAULT_EMBEDDING_MODEL`, `DEFAULT_QDRANT_COLLECTION`, `CORS_ORIGINS` (25 lines) |
| `/home/home/projects/ai-site-agent/.env` | `home:home` **644** | same key set (dev checkout) |
| `deploy/deploy.local.conf` | `home:home` **644** | `PROJECT_ROOT`, `DEV_CHECKOUT`, `BACKEND_DIR`, `DASHBOARD_DIR`, `VENV_DIR`, `FRONTEND_BUILD_DIR`, `ENV_FILE`, `BACKUP_DIR`, `LOG_DIR`, `APP_USER`, `APP_GROUP`, `HEALTHCHECK_URL`, `GIT_PULL_DEFAULT`, `NPM_BIN`, `NODE_BIN`, **`STAGING_ADMIN_PASSWORD`** (37 lines) |

Actual secret material is narrow: the **Postgres password inside `DATABASE_URL`** and
**`STAGING_ADMIN_PASSWORD`**. Everything else is host paths and non-sensitive settings.

### Findings and requirements

| # | Finding / requirement |
|---|----------------------|
| S1 | **Hardening opportunity:** `deploy.local.conf` contains `STAGING_ADMIN_PASSWORD` at mode **644** (world-readable), while `/opt/.env` is correctly **600**. The new host should create it **600** from the start. Recorded as an observation — **no change is authorized on the old host by this review.** |
| S2 | The dev-checkout `.env` is also 644 and duplicates `DATABASE_URL`; same treatment |
| S3 | Both files are gitignored and must **never** be committed |
| S4 | Transfer via a secure channel only — never a shared clipboard, ticket, chat message, or git |
| S5 | Prefer **re-creating** secrets on the new host from `.env.example` / `.env.staging.example` (both present in `/opt`) and rotating the DB password, over copying files verbatim |
| S6 | If the DB password is rotated, `DATABASE_URL` must be updated **before** the backend starts, or the restore-verification step will fail confusingly |

---

## 11. GitHub authentication

**DETERMINED — and this is a real gap, not a formality.**

| Property | Measured value |
|----------|----------------|
| Remote | `https://github.com/marioghost/ai-site-agent.git` (HTTPS, fetch and push) |
| `credential.helper` | **`<none>`** |
| `gh` CLI | **not installed** |
| SSH keys | **none** (`~/.ssh` has no keypair) |
| `~/.gitconfig` | present, 48 bytes; **no `user.name` / `user.email`** — commits are attributed to `root <root@DESKTOP-I2KQV1N.localdomain>` from system defaults |

**Consequence, observed directly during this task:** a non-interactive `git push origin main` fails
with `could not read Username for 'https://github.com'`. Pushes on this host therefore require
interactive credential entry. That is a workable but undocumented dependency, and it will silently
break any automation assumed to work on the new host.

| # | Requirement |
|---|-------------|
| G1 | Choose an explicit auth method on the new host: SSH key, `gh auth login`, or a credential helper with a PAT |
| G2 | Do **not** copy credentials from the old host; provision fresh and revoke old if a PAT was used |
| G3 | Set `user.name` / `user.email` explicitly so commit attribution is meaningful rather than `root@<hostname>` |
| G4 | Verify **fetch and push** before the cutover — `verify-release` requires `local main == origin/main`, so a broken fetch blocks the validation gate |
| G5 | Record the method in operator docs; it is currently undocumented |

---

## 12. `/opt` deployment layout

**DETERMINED.**

```text
/opt/ai-site-agent/                 home:home 755
├── .build-info.json                home:home 644   deploy identity (release + commit)
├── .env                            home:home 600   secrets
├── .env.example / .env.staging.example
├── .cursor/ .github/ .gitattributes .gitignore
├── Makefile  README.md  LICENSE
├── backend/                        home:home 755   366 MB (includes .venv)
├── dashboard/                      home:home 755   209 MB (node_modules + dist/.deploy-identity.json)
├── deploy/                         home:home 755   220 KB
├── docs/  scripts/
├── backups/                        home:home 775   809 MB
├── logs/                           home:home 775   624 KB
└── deployments/                    root:root 755   deploy manifests
```

Layout is defined by `deploy/deploy.local.conf`:

| Key | Value |
|-----|-------|
| `PROJECT_ROOT` | `/opt/ai-site-agent` |
| `DEV_CHECKOUT` | `/home/home/projects/ai-site-agent` |
| `VENV_DIR` | `/opt/ai-site-agent/backend/.venv` |
| `FRONTEND_BUILD_DIR` | `/opt/ai-site-agent/dashboard/dist` |
| `APP_USER` / `APP_GROUP` | **`home` / `home`** |
| `GIT_PULL_DEFAULT` | **`no`** — `/opt` is never a git remote target |
| `NPM_BIN` / `NODE_BIN` | absolute nvm paths |

### Two hazards to carry forward

**Hazard 1 — nvm under sudo.** `deploy.local.conf` documents it verbatim: *"sudo drops nvm from
PATH — point the dashboard build at the real node/npm."* `NODE_BIN` and `NPM_BIN` are absolute
paths into `/home/home/.nvm/versions/node/v20.20.2/bin/`. On the new host these paths **will not
match** unless nvm and the same Node version are installed for the same user. If Node is installed
system-wide instead, both keys must be updated. A stale `NPM_BIN` fails at the `deploy full` build
stage — after the backup, before the sync — which is a recoverable but noisy failure point.

**Hazard 2 — `APP_USER=home`, not `www-data`.** The comment explains why: *"WSL local: deploy runs
as user `home`. Using www-data here makes `fix_ownership` lock the tree mid-deploy (backup/rsync/npm
fail on the next run)."* This is a deliberate, hard-won setting. The new host must define `APP_USER`
to match whichever user actually owns `/opt` and runs the backend unit, and it must be consistent
across `deploy.local.conf`, the systemd `User=`, and filesystem ownership. Inconsistency here breaks
deploys **on the run after** the mistake, which makes it hard to diagnose.

**Code provenance rule (unchanged, and mandatory):** `/opt` is populated by rsync from a **clean
`origin/main` worktree** created by `deploy full`, never by copying the developer checkout and never
by `git pull` in `/opt`. `GIT_PULL_DEFAULT="no"` enforces the latter.

---

## 13. systemd units

**DETERMINED.**

| Unit | File | Enabled / Active | User | Notes |
|------|------|------------------|------|-------|
| `ai-agent-backend.service` | `/etc/systemd/system/` (531 B) | enabled / active | `home:home` | project-specific |
| `qdrant.service` | `/etc/systemd/system/` (394 B) | enabled / active | `qdrant:qdrant` | project-specific |
| `ollama.service` | `/etc/systemd/system/` (1020 B) | enabled / active | `ollama:ollama` | vendor-installed |
| `nginx.service` | packaged | enabled / active | root | distro default |
| `postgresql.service` | packaged | enabled / active | `postgres` | distro default |

### Backend unit — the dependency graph that must be preserved

```ini
[Unit]
After=network.target qdrant.service ollama.service
Wants=qdrant.service

[Service]
User=home
Group=home
WorkingDirectory=/opt/ai-site-agent/backend
Environment=PATH=/opt/ai-site-agent/backend/.venv/bin
EnvironmentFile=-/opt/ai-site-agent/.env
ExecStart=/opt/ai-site-agent/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
```

Note `EnvironmentFile=-/opt/ai-site-agent/.env` — the leading `-` means a **missing `.env` is not a
startup error**. The backend would start with defaults and a wrong or absent `DATABASE_URL`. On a
fresh host that turns a missing-secrets mistake into a confusing runtime failure instead of a clean
startup failure. Verify `.env` presence explicitly; do not rely on the unit to catch it.

### Qdrant unit

```ini
ExecStart=/opt/qdrant/qdrant --config-path /opt/qdrant/config.yaml
User=qdrant
Group=qdrant
WorkingDirectory=/opt/qdrant
LimitNOFILE=65536
```

`LimitNOFILE=65536` is required — Qdrant's segment files exhaust default limits.

### Ollama unit — contains machine-specific pollution

`ollama.service` carries an `Environment="PATH=…"` that includes
`/home/home/.cursor-server/bin/<build-hash>/bin/remote-cli` **and Windows `/mnt/c/...` paths**. This
is an artifact of the installer inheriting an interactive WSL shell environment.

| # | Requirement |
|---|-------------|
| U1 | **Do not copy `ollama.service` verbatim.** Install Ollama natively on the new host and let it generate its own unit |
| U2 | Recreate `ai-agent-backend.service` and `qdrant.service` from the versioned templates in `deploy/`, adjusting `User`/`Group`/paths — not by copying from the old host |
| U3 | Preserve the `After=`/`Wants=` ordering so the backend never starts before Qdrant and Ollama |
| U4 | Preserve `LimitNOFILE=65536` on Qdrant |
| U5 | If the new host lacks systemd as PID 1, an equivalent supervisor must express U3 and U4 — and `deploy full`'s restart stage, which shells out to `systemctl`, must be re-validated |

---

## 14. nginx configuration

**DETERMINED.**

Single site: `/etc/nginx/sites-enabled/ai-site-agent` → `/etc/nginx/sites-available/ai-site-agent`.
`conf.d/` is empty. nginx 1.24.0.

```nginx
server {
    listen 80;
    server_name localhost;
    root /opt/ai-site-agent/dashboard/dist;
    index index.html;

    location / { try_files $uri $uri/ /index.html; }   # SPA routing

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    client_max_body_size 20m;
}
```

| # | Requirement |
|---|-------------|
| N1 | Preserve `proxy_read_timeout 300s` — LLM generation exceeds the 60 s default; a shorter timeout produces intermittent 504s under load |
| N2 | Preserve `client_max_body_size 20m` — document upload |
| N3 | Preserve SPA `try_files` fallback, or dashboard deep links 404 |
| N4 | `root` must track `FRONTEND_BUILD_DIR` from `deploy.local.conf` |
| N5 | `server_name localhost` and plain `listen 80` are **local-only** settings. If the new host is network-reachable, TLS and a real `server_name` are **new configuration requiring their own review** — not part of this migration |
| N6 | Validate with `nginx -t` before reload, as `deploy full` already does |

---

## 15. Firewall and ports

**DETERMINED — with a finding.**

| Port | Bind | Service | Exposure |
|------|------|---------|----------|
| **80** | **`0.0.0.0`** | nginx | **all interfaces** |
| 8000 | `127.0.0.1` | backend | loopback |
| 5432 | `127.0.0.1` | PostgreSQL | loopback |
| 6333 | `127.0.0.1` | Qdrant HTTP | loopback |
| 6334 | `127.0.0.1` | Qdrant gRPC | loopback |
| 11434 | `127.0.0.1` | Ollama | loopback |
| 53 | `127.0.0.53/54` | systemd-resolved | local |

**Finding: there is no host firewall.** `ufw` is not installed and `iptables` is not present. The
current protection is **bind-address discipline plus WSL2 network isolation** — not filtering. Five
of six services are unreachable from outside because they bind loopback, and that is the entire
control.

| # | Requirement |
|---|-------------|
| F1 | Reproduce loopback binds exactly for backend, Postgres, Qdrant, Ollama |
| F2 | If the new host is on a routable network, WSL2 isolation no longer substitutes for a firewall. A real firewall policy is then **required new work**, scoped and reviewed separately |
| F3 | Do not expose 5432 / 6333 / 6334 / 11434 during migration for transfer convenience; use SSH tunnels or file transfer |
| F4 | Verify post-migration with `ss -lntup` and compare against this table |

---

## 16. Filesystem ownership and permissions

**DETERMINED.**

| Path | Owner | Mode | Note |
|------|-------|------|------|
| `/opt/ai-site-agent` | `home:home` | 755 | `APP_USER`/`APP_GROUP` |
| `/opt/ai-site-agent/.env` | `home:home` | **600** | correct |
| `/opt/ai-site-agent/backups` | `home:home` | 775 | group-writable |
| `/opt/ai-site-agent/logs` | `home:home` | 775 | group-writable |
| `/opt/ai-site-agent/deployments` | **`root:root`** | 755 | **inconsistent with the rest of the tree** |
| `/var/lib/postgresql/16/main` | `postgres` | — | cluster data |
| `/var/lib/qdrant/storage` | `qdrant:qdrant` | — | matches unit `User=` |
| `/usr/share/ollama/.ollama/models` | `ollama:ollama` | — | matches unit `User=` |
| `deploy/deploy.local.conf` | `home:home` | **644** | see S1 |

`deployments/` being `root:root` while its parent is `home:home` is a real inconsistency: it is
written by `deploy full` under `sudo`. It works today, but on a new host it is the kind of drift
that makes `fix_ownership` behave unexpectedly.

| # | Requirement |
|---|-------------|
| W1 | Choose one runtime user and apply it consistently: `deploy.local.conf` `APP_USER`/`APP_GROUP`, systemd `User=`/`Group=`, and `/opt` ownership must all agree |
| W2 | `.env` must be **600** from creation, before any secret is written into it |
| W3 | Service data directories must be owned by their unit's `User=` (`postgres`, `qdrant`, `ollama`) |
| W4 | Decide `deployments/` ownership deliberately rather than inheriting the `root:root` accident |
| W5 | Re-read the `www-data` warning in §12 before choosing `APP_USER` |

---

## 17. Backup retention

**DETERMINED — with a finding.**

| Metric | Measured value |
|--------|----------------|
| `backups/` total | **809 MB** |
| Dump count | **51** `.dump` files |
| Oldest | `ai_site_agent.20260630_144937.dump` (2026-06-30) |
| Newest | `ai_site_agent.20260729_095751.dump` (2026-07-29) |
| Span | ~29 days |
| Release archive | `backups/releases/0.7/` — dump + `.list` + `.meta.json` |
| Other artifacts | `backups/cutback/`, `backups/forensic/`, legacy `app.db.backup.*` SQLite files, `ai_site_agent_recovery.20260728_010704.dump` |
| Logs | 624 KB, 89 files |
| Deploy manifests | 2 |

**Finding: retention is unbounded.** 51 dumps accumulated in 29 days because every `deploy full`
takes a mandatory backup and nothing prunes. At ~11.6 MB each this is currently harmless on a 934 GB
volume, but it is unmanaged growth, and it means "the backups directory" is not a curated set.

The `releases/0.7/` pattern — dump plus `pg_restore --list` plus `meta.json` — is notably better
than the flat timestamped dumps, and is the pattern worth standardizing.

| # | Requirement |
|---|-------------|
| B1 | Do **not** bulk-copy 809 MB of historical dumps to the new host. Migrate deliberately: the three Release 0.8 dumps (report §3) plus `releases/0.7/` |
| B2 | Retain the old host's `backups/` in place for the rollback window; it is rollback material |
| B3 | Define an explicit retention policy on the new host (count or age based). Proposing one is **new work**, not part of this migration |
| B4 | Legacy SQLite `app.db.backup.*` artifacts predate PostgreSQL — classify as archive or delete; do not migrate as live |
| B5 | Decide `cutback/` and `forensic/` disposition explicitly |
| B6 | Adopt the `releases/<version>/` dump + `.list` + `.meta.json` convention |

---

## 18. Cutover plan

**DEFERRED — depends on §2, §3, §5, and §8.**

A cutover plan cannot be finalized without the target topology and the chosen downtime window. What
**is** determined now is the ordering invariant, which holds under every option:

```text
pre-stage (immutable)  →  FREEZE  →  capture  →  transfer  →  restore  →  verify  →  cutover
```

| Phase | Invariant | Basis |
|-------|-----------|-------|
| Pre-stage | OS packages, clean `origin/main` clone, Ollama models, Qdrant binary — all before the freeze | §5: immutables must not consume window |
| **Freeze** | stop `ai-agent-backend.service`; confirm no `index_jobs` running | §5: backend is the sole writer |
| Capture | `backup db` **and** Qdrant snapshots from the **same** frozen instant | §4: Postgres and Qdrant are one atomic unit |
| Transfer | checksum before and after | §6, §7 |
| Restore | roles/DB first, then restore, then Qdrant, then verify counts | P1–P8, §7 |
| Schema | if `/opt` on the new host lacks migration files that `origin/main` requires, use `bash deploy/manage_deploy.sh migrate release` — **the only supported schema-first command** | proven in Release 0.8 |
| Deploy | `sudo bash deploy/manage_deploy.sh deploy full` from clean `origin/main` | §12 provenance rule |
| Verify | `health`, `build-info`, `smoke`, `verify-release` — all must pass | §20 |
| Cutover | flip access only **after** verification | §3: one writer at a time |

The validated command order is the Release 0.8 canonical sequence, already proven on this host:

```text
status → backup db → migrate release → verify schema head
→ deploy full → health → build-info → smoke → verify-release
```

Restoring a dump that already contains `0019` makes the schema-first step a **no-op by construction**
— but `deploy full`'s internal post-sync Alembic upgrade will still run as an idempotent
defense-in-depth check, exactly as observed in Release 0.8
([report §5](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md)). Expect no `Running upgrade` lines.

Still to be decided in Part 2: absolute sequencing and timing, who approves the flip, how access is
redirected, and the go/no-go checkpoints.

---

## 19. Rollback to old machine

**PARTIALLY DETERMINED — mechanism clear; trigger criteria deferred.**

The old host is a **complete, running, verified system** at Release 0.8 / `39ebef1` / Alembic `0019`,
with 51 dumps and its full corpus. That is the strongest possible rollback position, and it stays
valid **as long as the old host is not mutated.**

| # | Requirement |
|---|-------------|
| K1 | Do **not** decommission, wipe, or upgrade the old host until new-machine acceptance is recorded |
| K2 | Do **not** delete `/opt/ai-site-agent/backups` on the old host during the rollback window |
| K3 | Keep the old host **frozen** (backend stopped) during the window — do not let it resume writing, or the two hosts diverge |
| K4 | Rollback = restart the old host's backend and redirect access back; **no restore is needed** because its state was never mutated |
| K5 | Never "fix" a rollback by clearing Qdrant or re-running indexing |
| K6 | Record explicitly which host is authoritative at every moment of the window |
| K7 | If the new host accepted **any** write before rollback, those writes are **discarded** — there is no merge path. Accept this or do not allow writes before acceptance |

Deferred: rollback trigger criteria, decision owner, and the rollback-window duration.

---

## 20. Acceptance criteria

**PARTIALLY DETERMINED — technical criteria derived from the Release 0.8 baseline; sign-off owners deferred.**

Every criterion below is measurable with existing tooling and has a known-good value from the
Release 0.8 deployment.

### Identity and schema

| # | Criterion | Expected |
|---|-----------|----------|
| A1 | `verify-release` verdict | **PASS**, `FAIL=0` |
| A2 | Identity chain | `origin/main` == build-info == frontend == `/api/build` |
| A3 | `release` | `0.8` |
| A4 | `alembic_head` | `0019_legacy_doc_type_canonical_enabled` |
| A5 | `/api/health` | `app`, `ollama`, `qdrant`, `database` all `ok` |
| A6 | Code provenance | `/opt` populated from clean `origin/main`; **no** dirty-tree copy |

### Data integrity — must match exactly

| # | Criterion | Expected |
|---|-----------|----------|
| A7 | sources / chunks | **5023** / **17958** |
| A8 | claims / observations / evidence links | **39** / **13** / **21** |
| A9 | `knowledge_version` / `memory_version` | **26** / **177** |
| A10 | Qdrant `site_knowledge` | **18780** points, `green` |
| A11 | Vector config | size **1024**, distance **Cosine** |
| A12 | `bge-m3` digest | **matches** the old host (O1–O3) |

### Configuration and flags

| # | Criterion | Expected |
|---|-----------|----------|
| A13 | All 11 experimental flags | **false** on both settings rows |
| A14 | `allow_legacy_kp_presets`, `legacy_doc_type_canonical_enabled` | **false**, defaults `false NOT NULL` |
| A15 | `staging_validated` / `production_ready` | **`false`** / **`false`** |
| A16 | Listening ports | match §15; only nginx non-loopback |
| A17 | Ownership | consistent per W1; `.env` mode **600** |

### Functional

| # | Criterion | Expected |
|---|-----------|----------|
| A18 | `smoke` | pass — 6 HTTP checks + golden parity |
| A19 | Golden parity tests | **41 passed** |
| A20 | Dashboard | loads; deep links resolve (N3) |
| A21 | Chat + follow-up | grounded answers with sources |
| A22 | No unintended writes | claim count still 39; no new `index_jobs` |

### Explicit non-criteria

| Item | Why not a criterion |
|------|--------------------|
| Response-time parity with the old host | new hardware invalidates the baseline (§8); measure and record, do not gate |
| `staging_validated=true` | machine migration is **not** staging validation. `DEBT-0.8-001` and the §13 Step 055 finding in the deployment report gate that independently |
| `production_ready=true` | gated behind Staging Validated |
| Step 055 / Russian-query quality | pre-existing (`DEBT-0.8-001`); must **not** become a migration blocker or a migration excuse |

Deferred: sign-off owners, acceptance meeting, and rollback-window closure criteria.

---

## Risks carried forward

| Risk | Severity | Mitigation |
|------|----------|------------|
| `bge-m3:latest` re-pull yields different embeddings | **High** — silent retrieval degradation | O1–O3: record and verify digest |
| Postgres/Qdrant captured at different instants | **High** — silent version skew | §4: one atomic frozen instant |
| Dual-write during parallel run | **High** — unreconcilable divergence | §3 option C forbidden; K3, K7 |
| Stale `NPM_BIN`/`NODE_BIN` on new host | **Medium** — `deploy full` fails at build | §12 hazard 1 |
| `APP_USER` inconsistency | **Medium** — breaks the *next* deploy | W1, §12 hazard 2 |
| Copying `ollama.service` with Cursor/Windows PATH | **Medium** — fragile unit | U1 |
| Missing `.env` not failing startup (`EnvironmentFile=-`) | **Medium** — confusing runtime failure | §13: verify explicitly |
| Old host mutated during rollback window | **High** — destroys rollback | K1–K3 |
| Reduced RAM vs 7.7 GiB running a 7.6 B model | Medium | R6; confirm new-host RAM |
| No firewall once off WSL2 isolation | **Medium** | F2 — separate scoped work |
| Bulk-copying 809 MB of stale dumps | Low | B1 |
| `ai_site_agent_recovery` mistaken for live | **Medium** — wrong `DATABASE_URL` | §6 explicit decision |

Housekeeping observation: three stale git worktrees are registered from `/tmp`
(`ai-site-agent-0.7`, `ai-site-agent-deploy-hSNs3M`, `ai-site-agent-release-0.7`). `/tmp` does not
survive restarts, so these are dangling registrations. A clean clone on the new host will not carry
them; `git worktree prune` on the old host is optional and **not authorized here**.

---

## Required inputs before Part 2

Part 2 cannot be written without these. Nothing else blocks it.

| # | Input | Unblocks |
|---|-------|----------|
| 1 | New-machine OS and version | §2, R1–R4 |
| 2 | Bare metal / VM / WSL2 / container | §2, §13 (U5), §15 (F2) |
| 3 | CPU, RAM, disk | §2 (R5, R6) |
| 4 | **GPU model and VRAM** | §8, §20 non-criteria |
| 5 | **systemd available as PID 1?** | §13 (U5) |
| 6 | New host = sole runtime host, or parallel window? | §3, §18, §19 |
| 7 | Acceptable downtime / write-freeze window | §5, §18 |
| 8 | Network reachability and TLS requirement | §14 (N5), §15 (F2) |
| 9 | Chosen secure channel for secrets | §10 |
| 10 | Chosen GitHub auth method | §11 |
| 11 | Rotate the DB password, or carry it over? | §10 (S5, S6) |
| 12 | `ai_site_agent_recovery` disposition | §6 |
| 13 | Rollback-window duration and decision owner | §19 |
| 14 | Sign-off owners | §20 |

---

## Determination status

| Item | Status |
|------|--------|
| 1. Old-machine topology | **DETERMINED** |
| 2. New-machine topology and OS | **DEFERRED** (requirements R1–R8 recorded) |
| 3. Runtime host | **DEFERRED** (options + invariant recorded) |
| 4. Do PG/Qdrant/Ollama move together | **PARTIAL** — coupling determined |
| 5. Downtime / write-freeze | **PARTIAL** — mechanism determined |
| 6. PostgreSQL backup/restore | **DETERMINED** |
| 7. Qdrant snapshot/restore | **DETERMINED** |
| 8. Ollama transfer vs re-pull | **DEFERRED** — constraints O1–O4 recorded |
| 9. Cursor migration | **PARTIAL** — inventory determined |
| 10. Secrets transfer | **PARTIAL** — inventory determined |
| 11. GitHub authentication | **DETERMINED** (gap found) |
| 12. `/opt` layout | **DETERMINED** (2 hazards) |
| 13. systemd units | **DETERMINED** |
| 14. nginx configuration | **DETERMINED** |
| 15. Firewall and ports | **DETERMINED** (no firewall) |
| 16. Ownership and permissions | **DETERMINED** (1 inconsistency) |
| 17. Backup retention | **DETERMINED** (unbounded) |
| 18. Cutover plan | **DEFERRED** — invariant recorded |
| 19. Rollback | **PARTIAL** — mechanism determined |
| 20. Acceptance criteria | **PARTIAL** — A1–A22 derived |

**11 determined, 5 partial, 4 deferred.** Every deferred item is blocked solely on the inputs above,
and no deferred item hides an unmade technical decision — the constraints are recorded so Part 2 is
a decision exercise, not a discovery exercise.

---

## Review status

| Gate | State |
|------|-------|
| Part 1 (old machine + requirements) | **complete, awaiting review** |
| Part 2 (new machine + cutover) | **blocked** on required inputs |
| Architecture review approval | **NOT GRANTED** |
| Migration execution | **NOT AUTHORIZED** |
| Old host | **remains authoritative and untouched** |
| Release 0.9 | **blocked** |

**Nothing was executed, changed, restored, transferred, or cut over to produce this document.** All
findings are read-only measurements taken 2026-07-29.

---

## Sign-off (fill at approval time)

| Role | Name | Date |
|------|------|------|
| Ops lead | | |
| Engineering | | |
| Architecture review approver | | |
| Cutover approver | | |
