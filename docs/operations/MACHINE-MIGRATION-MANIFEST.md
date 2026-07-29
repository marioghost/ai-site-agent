# Machine Migration Manifest — canonical blueprint

**Status:** **Architecture and planning only. NOT approved. NOT executed.**  
**Phase:** Post-0.8 Machine Migration Architecture Review — **Part 2 (final)**  
**Date:** 2026-07-29  
**Base:** `main` @ `1c8c16e`  
**Part 1:** [POST-0.8-MACHINE-MIGRATION-ARCHITECTURE-REVIEW.md](POST-0.8-MACHINE-MIGRATION-ARCHITECTURE-REVIEW.md) — measured old-machine baseline  
**Plan of record:** [POST-0.8-MACHINE-MIGRATION.md](POST-0.8-MACHINE-MIGRATION.md)  
**Deployment evidence:** [RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md](RELEASE-0.8-OPERATIONAL-DEPLOYMENT-REPORT.md)

**Public operator entry point on every host:**

```bash
bash deploy/manage_deploy.sh <command>
```

**Frozen production baseline (unchanged by this document):**

| Property | Value |
|----------|-------|
| Release | **0.8** |
| `origin/main` == `/opt` == `/api/build` | `39ebef1b76a4236a8e608d7300cbecf0107f75b4` |
| Alembic head | `0019_legacy_doc_type_canonical_enabled` |
| Engineering Ready / Runtime Validated | **PASS** / **PASS** |
| Staging Validated / Production Ready | **false** / **false** |
| Authoritative runtime | **the current machine, and only the current machine** |

> **This document authorizes nothing.** No execution, deploy, restore, data copy, Qdrant access,
> production change, or Release 0.9 work. Every command shown is a **planned** command.

---

## 1. Resolved unknowns

All twenty required determinations are now closed. Fourteen were resolved by measurement on the old
host; six are **architecture decisions recorded here as PROPOSED**, each with rationale, awaiting
sign-off rather than further investigation.

| # | Question | Resolution | Basis |
|---|----------|-----------|-------|
| 1 | New machine OS + version | **MANDATED: Ubuntu 24.04 LTS (Noble)** | parity with old host; R1–R4 satisfied by distro packages |
| 2 | Bare metal / VM / WSL2 / container | **MANDATED: any, provided systemd is PID 1** and loopback binds are possible | §2 requirement R7; not a free choice |
| 3 | CPU | **MANDATED minimum: 8 cores x86-64** (old host: 16 logical, i9-9880H) | CPU-only inference baseline |
| 4 | RAM | **MANDATED minimum: 16 GB** (old host: 7.7 GiB — currently constrained) | R6; raises headroom rather than reproducing a bottleneck |
| 5 | Storage | **MANDATED minimum: 100 GB free, ext4** | measured need ~12 GB + growth + retention (§18) |
| 6 | GPU model | **OPTIONAL — plan handles both branches** | old host has **no CUDA GPU**; GPU is an improvement, not a requirement |
| 7 | GPU VRAM | **≥ 8 GB if GPU present** (to run `qwen2.5:7b`); otherwise N/A | `deploy/OLLAMA.md`: 7B is GPU-appropriate, too slow on CPU |
| 8 | systemd as PID 1 | **MANDATED: yes** | old host achieves this via `/etc/wsl.conf` `systemd=true`; `deploy full` restart stage shells out to `systemctl` |
| 9 | Static IP / DHCP | **PROPOSED: static IP or DHCP reservation** | old host is WSL2 NAT `172.26.224.147/20` via `172.26.224.1` — **ephemeral**; unstable addressing blocks any future TLS |
| 10 | Local only or Internet reachable | **PROPOSED: local only** for the migration | old host is local-only today; exposure is separate scoped work |
| 11 | TLS strategy | **PROPOSED: SKIP** (no TLS in migration scope) | no certs, no certbot, no `443` config exist today; adding TLS is new work needing its own review |
| 12 | SSH strategy | **PROPOSED: GENERATE** ed25519, key-only, no password auth; `openssh-server` on the **new** host only | old host has **no sshd and no keys**, but has an ssh **client** — so it can push without being modified as a server |
| 13 | Git authentication | **PROPOSED: GENERATE** SSH deploy key for `git@github.com`; set `user.name`/`user.email` explicitly | old host has no helper, no `gh`, no keys — pushes are interactive-only today (§11 Part 1) |
| 14 | Secrets transfer | **PROPOSED: GENERATE + ROTATE — do not copy** | secret surface is only the DB password and `STAGING_ADMIN_PASSWORD`; recreate from `.env.example` |
| 15 | Downtime window | **PROPOSED: 60 min approved, ~30 min technical target** | evidence-based, see §5 |
| 16 | Final runtime hostname | **REQUIRES USER VALUE** — a stable name, not `DESKTOP-*` | low blast radius: nginx uses `server_name localhost`, `CORS_ORIGINS` references only localhost |
| 17 | Firewall policy | **PROPOSED: `ufw` default-deny inbound**, allow 22/tcp from admin source, 80/tcp local only | old host has **no firewall at all** — protection is bind-discipline plus WSL2 isolation |
| 18 | Backup retention | **PROPOSED: 14 daily + 4 weekly + all release-tagged; add logrotate** | old host: **51 dumps / 809 MB unbounded**, and **no app logrotate** |
| 19 | Fate of `ai_site_agent_recovery` | **DECIDED: SKIP as a live database**; archive one final dump to cold storage | nothing in the app references it; carrying it invites a wrong `DATABASE_URL` |
| 20 | Rollback window | **PROPOSED: until acceptance + 14 days of normal operation** | old host is a complete verified system; its value as rollback decays only when the new host is proven |

### Newly measured facts that changed the plan

Four measurements taken for Part 2 materially altered the blueprint.

**Model digests are now pinned.** Part 1 required these before migration (O1); they are recorded:

| Model | Digest | Blob | Role |
|-------|--------|------|------|
| `bge-m3:latest` | `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab` | `sha256-daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c` | **embeddings — critical** |
| `qwen2.5:3b` | `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` | — | **runtime LLM** |
| `qwen2.5:7b` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | — | optional / GPU-only |

`bge-m3` internals confirm the Qdrant pairing exactly: `bert.embedding_length = 1024`,
`context_length = 8192`, `F16`, architecture `bert`. This is the hard link to the 18780 stored
vectors.

**Correction to Part 1: `qwen2.5:3b` is the runtime LLM, not `qwen2.5:7b`.** Part 1 labelled the 7B
model "primary". Evidence says otherwise: `.env` sets `DEFAULT_LLM_MODEL=qwen2.5:3b` and
`OLLAMA_WARMUP_MODEL=qwen2.5:3b`; migration `0009_cpu_local_model_defaults` sets
`llm_model='qwen2.5:3b'`; `docs/STAGING-SEED-SMOKE.md` requires only `qwen2.5:3b` and `bge-m3` for
smoke; and `deploy/OLLAMA.md` states plainly that *"CPU-only `qwen2.5:7b` is often too slow for
interactive chat (50 s+ time-to-first-token)"*. Part 1 has been corrected in the same commit as this
document.

**Consequence — the critical-path model payload drops from 7.77 GB to 3.09 GB.** Only `bge-m3`
(1.16 GB) and `qwen2.5:3b` (1.93 GB) are required. `qwen2.5:7b` (4.68 GB) is deferred and only worth
pulling if the new host has a GPU. This removes 60 % of the largest transfer item from the cutover.

**Database collation is a hard restore constraint that Part 1 missed.** All three databases are
`encoding=UTF8, collate=C.UTF-8, ctype=C.UTF-8`, and the host is `LANG=C.UTF-8`,
timezone `Europe/Simferopol (MSK, +0300)`. Collation is fixed at `initdb`/`CREATE DATABASE` time and
cannot be changed afterward without recreating the database. A mismatched collation lets
`pg_restore` **succeed** while silently changing text index ordering and comparison results.

**No application-level scheduled work exists.** `/etc/crontab` holds only distro `run-parts`
entries; `cron.d` has only `e2scrub_all` and `sysstat`; **all user crontabs are empty** (root, home,
postgres, qdrant, ollama); systemd timers are distro-only. There is also **no logrotate config for
`/opt/ai-site-agent/logs`** — which, with unbounded backups, confirms §18.

---

## 2. Target machine fact sheet

The mandated platform is the contract. Fill the confirmed column at provisioning; any deviation
triggers the listed handling rather than silent acceptance.

| # | Property | Mandated | Confirmed | Handling if different |
|---|----------|----------|-----------|----------------------|
| 1 | OS | Ubuntu 24.04 LTS | ☐ | Debian 12 acceptable if PG 16 + Python 3.12 available; other distro ⇒ re-review R1–R4 |
| 2 | Platform | bare metal / VM / WSL2 / container | ☐ | any, **if** systemd is PID 1 |
| 3 | CPU cores | ≥ 8 x86-64 | ☐ | < 8 ⇒ record slower baseline; not a blocker |
| 4 | RAM | ≥ 16 GB | ☐ | < 8 GB ⇒ **blocker** (old host already tight at 7.7 GiB) |
| 5 | Free disk | ≥ 100 GB ext4 | ☐ | < 20 GB ⇒ **blocker** |
| 6 | GPU | optional | ☐ | absent ⇒ skip `qwen2.5:7b`; present ⇒ pull it and record new baseline |
| 7 | GPU VRAM | ≥ 8 GB if GPU | ☐ | < 8 GB ⇒ treat as CPU-only for the 7B model |
| 8 | systemd PID 1 | **required** | ☐ | absent ⇒ **blocker** until `deploy full` restart stage is re-validated (U5) |
| 9 | Addressing | static or DHCP reservation | ☐ | pure DHCP ⇒ acceptable local-only; blocks TLS later |
| 10 | Exposure | local only | ☐ | internet ⇒ TLS + firewall become **required separate work** |
| 11 | Locale | `C.UTF-8` available **before `initdb`** | ☐ | mismatch ⇒ **blocker** (collation) |
| 12 | Timezone | `Europe/Simferopol` (or documented change) | ☐ | change ⇒ record; timestamps are `timestamptz` so data is safe |
| 13 | PostgreSQL | **16.x** | ☐ | < 16 ⇒ **blocker**; > 16 ⇒ acceptable, verify restore |
| 14 | Python | 3.12.x | ☐ | other minor ⇒ re-validate `requirements.txt` |
| 15 | Node | 20.20.2 via nvm as `APP_USER` | ☐ | system Node ⇒ **must update `NPM_BIN`/`NODE_BIN`** |
| 16 | Qdrant | 1.12.4 | ☐ | other ⇒ verify 1.12 snapshot restore path first |
| 17 | Hostname | stable, non-`DESKTOP-*` | ☐ | — |

---

## 3. Migration manifest

**Classification vocabulary** (exactly one per component):

| Class | Meaning |
|-------|---------|
| **COPY** | byte-for-byte transfer of existing artifact |
| **RESTORE** | reconstruct from a validated backup/snapshot |
| **REBUILD** | regenerate from source on the target |
| **REINSTALL** | install fresh from package/vendor |
| **RE-PULL** | fetch from an upstream registry |
| **GENERATE** | create new on target (new value, not a copy) |
| **SKIP** | deliberately not migrated |

Owner codes: **OPS** = operator/infrastructure, **ENG** = engineering. Status is **PLANNED** for
every row — nothing is in progress.

### 3.1 Platform and toolchain

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| OS | REINSTALL | Ubuntu 24.04.4 LTS, WSL2 kernel 6.6.87.2 | new host | fresh install | `/etc/os-release`; `systemctl is-system-running` = `running`; `ps -p 1 -o comm=` = `systemd` | old host untouched | OPS | PLANNED |
| apt packages | REINSTALL | `postgresql-16`, `postgresql-contrib`, `nginx 1.24.0`, `build-essential`, `curl`, `git 2.43`, `rsync 3.2.7`, `ca-certificates`, `openssh-client` | new host | `apt install` | `dpkg -l` versions ≥ old | old host untouched | OPS | PLANNED |
| Locale / collation | GENERATE | `LANG=C.UTF-8` | new host, **before `initdb`** | `locale-gen` / `update-locale` | `locale`; `SHOW lc_collate` = `C.UTF-8` | recreate cluster | OPS | PLANNED |
| Timezone | GENERATE | `Europe/Simferopol` (MSK +0300) | new host | `timedatectl set-timezone` | `timedatectl`; NTP active | reconfigure | OPS | PLANNED |
| Runtime users/groups | GENERATE | `home:home` (APP_USER), `postgres`, `qdrant`, `ollama` | new host | `useradd` / package-created | `id <user>` for all four; matches unit `User=` | old host untouched | OPS | PLANNED |
| Python | REINSTALL | `/usr/bin/python3` 3.12.3 | `/usr/bin/python3` | `apt` | `python3 --version` = 3.12.x | — | OPS | PLANNED |
| Node | REINSTALL | nvm `v20.20.2` at `/home/home/.nvm/versions/node/v20.20.2` | same path **as APP_USER** | nvm install as APP_USER | `node -v` = v20.20.2; path matches `NODE_BIN` | — | OPS | PLANNED |
| Virtualenv | REBUILD | `/opt/ai-site-agent/backend/.venv` (366 MB) | same | **`deploy full` rebuilds** — never copy | `pip install -r requirements.txt` clean; backend imports | rebuild | ENG | PLANNED |
| Build artifacts | REBUILD | `/opt/ai-site-agent/dashboard/dist` + `node_modules` (209 MB) | same | **`deploy full` builds from clean worktree** | `.deploy-identity.json` commit == `origin/main` | rebuild | ENG | PLANNED |
| Firewall | GENERATE | **none** (`ufw` and `iptables` absent) | new host | `ufw` default deny inbound | `ufw status`; `ss -lntup` matches §3.4 | N/A (old host has none) | OPS | PLANNED |
| Certificates | SKIP | **none exist** (no letsencrypt, no certbot, no `443`) | — | not in scope | `ls /etc/letsencrypt` absent by design | N/A | OPS | PLANNED |
| cron | SKIP | **no app entries** — all user crontabs empty; distro-only | — | not migrated | `crontab -l` empty for all runtime users | N/A | OPS | PLANNED |
| logrotate (app) | GENERATE | **absent** for `/opt/ai-site-agent/logs` | `/etc/logrotate.d/ai-site-agent` | new config | `logrotate --debug` parses | N/A | OPS | PLANNED |
| Permissions | GENERATE | `/opt` `home:home` 755; `.env` **600**; `backups`/`logs` 775; `deployments` **root:root** | new host, consistent | set at build per W1–W5 | `stat` per §3.5; `.env` = 600 | old host untouched | OPS | PLANNED |

### 3.2 Code, repository, and deploy tooling

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| Git repository | REBUILD | `/home/home/projects/ai-site-agent` (608 MB, `.git` 13 MB) | `~/projects/ai-site-agent` | **clean `git clone`** — never rsync the dev checkout | on branch `main`, **not detached**; `main` == `origin/main` == `C_cut` (§6.1); `git status --porcelain` empty | old checkout intact | ENG | PLANNED |
| `origin` remote | GENERATE | `https://github.com/marioghost/ai-site-agent.git` | `git@github.com:marioghost/ai-site-agent.git` | reconfigure to SSH | `git fetch` and `git push --dry-run` both succeed | revert URL | ENG | PLANNED |
| `deploy/` | REBUILD | `/opt/ai-site-agent/deploy` (220 KB) | same | arrives with clone → `deploy full` sync | present in `/opt` after sync | — | ENG | PLANNED |
| `manage_deploy.sh` | REBUILD | `deploy/manage_deploy.sh` | same | in git; **sole operator entry point** | `bash deploy/manage_deploy.sh help` runs; `doctor` passes | — | ENG | PLANNED |
| `deploy.local.conf` | GENERATE | `deploy/deploy.local.conf` (mode **644**, gitignored) | same, **mode 600** | recreate; **update `NPM_BIN`/`NODE_BIN`/`APP_USER`** | `bash deploy/manage_deploy.sh status` resolves paths | old file intact | OPS | PLANNED |
| `/opt` deployment layout | REBUILD | `/opt/ai-site-agent` | same | `deploy full` rsync from clean `origin/main` worktree | `verify-release` **PASS**; `GIT_PULL_DEFAULT=no` | old `/opt` intact | ENG | PLANNED |
| systemd units | GENERATE | `ai-agent-backend.service`, `qdrant.service` in `/etc/systemd/system/` | same | recreate from `deploy/` templates — **do not copy** | `is-enabled`+`is-active`; `After=`/`Wants=` ordering; `LimitNOFILE=65536` | old units intact | OPS | PLANNED |
| `ollama.service` | REINSTALL | `/etc/systemd/system/ollama.service` — **contains Cursor build-hash and Windows `/mnt/c` PATH** | vendor-generated | Ollama installer generates its own | `is-active`; PATH contains **no** `/mnt/c` or `.cursor-server` | old unit intact | OPS | PLANNED |
| nginx | GENERATE | `/etc/nginx/sites-available/ai-site-agent` | same | recreate from repo template | `nginx -t`; `proxy_read_timeout 300s`; `client_max_body_size 20m`; SPA `try_files` | old config intact | OPS | PLANNED |
| logs | COPY | `/opt/ai-site-agent/logs` (624 KB, 89 files) | archive dir on new host | copy as **historical archive**, not live | files readable; not written by new runtime | old logs intact | OPS | PLANNED |

### 3.3 Data — the atomic pair

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| PostgreSQL cluster | REINSTALL | `/var/lib/postgresql/16/main`, PG 16.14 | same | `apt`; **`initdb` with `C.UTF-8`** | `SHOW server_version` ≥ 16; `lc_collate=C.UTF-8` | old cluster intact | OPS | PLANNED |
| `ai_agent` role | GENERATE | role in old cluster | new cluster | `CREATE ROLE` with **rotated** password | `\du` shows `ai_agent` with LOGIN | old role intact | OPS | PLANNED |
| `ai_site_agent` (DB) | **RESTORE** | 103 MB, Alembic `0019` | new cluster | `backup db` dump → `pg_restore` | `alembic_version`=`0019…`; sources **5023**, chunks **17958**, claims **39**, obs **13**, links **21**; `knowledge_version=26`, `memory_version=177`; 11 flags **false** | old DB untouched | ENG | PLANNED |
| `ai_site_agent_recovery` | **SKIP** | 107 MB, incident artifact | **not created** | final dump to cold storage only | `\l` shows **no** recovery DB on new host | remains on old host | ENG | PLANNED |
| Qdrant | REINSTALL | `/opt/qdrant/qdrant` 1.12.4 (73 MB) + `config.yaml` | same | download 1.12.4 binary; recreate config | `GET /` reports version 1.12.4 | old install intact | OPS | PLANNED |
| Qdrant `site_knowledge` | **RESTORE** | `/var/lib/qdrant/storage` (143 MB), 18780 pts | same | **native snapshot API** — not a filesystem copy | points **18780**, `status=green`, size **1024**, distance **Cosine** | old storage untouched | ENG | PLANNED |
| Qdrant `site_knowledge_answer_cache` | GENERATE | 7 points | same | **recreate empty** with identical 1024/Cosine config | collection exists, `green`, size 1024/Cosine | old storage untouched | ENG | PLANNED |
| backups | COPY | `/opt/ai-site-agent/backups` (809 MB, 51 dumps) | new host, **curated** | copy **only** the 3 Release 0.8 dumps + `releases/0.7/` | SHA256 match; `pg_restore --list` = 217 TOC / 19 TABLE DATA | **old backups stay in place** | OPS | PLANNED |

### 3.4 Services and network

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| Backend | REBUILD | `127.0.0.1:8000`, uvicorn under `ai-agent-backend.service` | same bind | `deploy full` | `/api/health` `app=ok`; bind is **loopback** | old backend restartable | ENG | PLANNED |
| PostgreSQL bind | GENERATE | `127.0.0.1:5432` | same | `postgresql.conf` | `ss -lntup` shows loopback only | — | OPS | PLANNED |
| Qdrant bind | GENERATE | `127.0.0.1:6333` HTTP, `:6334` gRPC | same | `config.yaml` `host: 127.0.0.1` | `ss -lntup` loopback only | — | OPS | PLANNED |
| Ollama bind | GENERATE | `127.0.0.1:11434` | same | default | `ss -lntup` loopback only | — | OPS | PLANNED |
| nginx bind | GENERATE | **`0.0.0.0:80`** — only non-loopback port | same (local only) | site config | `ss -lntup`; only port 80 non-loopback | — | OPS | PLANNED |
| Addressing | GENERATE | WSL2 NAT `172.26.224.147/20` gw `172.26.224.1` — **ephemeral** | static / reserved | network config | `ip -4 addr`; address stable across reboot | — | OPS | PLANNED |
| Hostname | GENERATE | `DESKTOP-I2KQV1N` | **user-supplied** | `hostnamectl set-hostname` | `hostnamectl --static` | — | OPS | PLANNED |

### 3.5 Models

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| Ollama runtime | REINSTALL | `/usr/local/bin/ollama` 0.30.10 | same | vendor installer | `/api/version` = 0.30.10 | old install intact | OPS | PLANNED |
| `bge-m3:latest` | **RE-PULL** (fallback COPY) | `/usr/share/ollama/.ollama/models` | same | `ollama pull bge-m3`; **if digest differs, COPY the blob instead** | digest == `7907646426…6bab`; `embedding_length=1024` | old models intact | ENG | PLANNED |
| `qwen2.5:3b` | **RE-PULL** | same | same | `ollama pull qwen2.5:3b` | digest == `357c53fb659c…9e4b`; present in `/api/tags` | old models intact | ENG | PLANNED |
| `qwen2.5:7b` | **RE-PULL (deferred)** | same | same, **only if GPU present** | `ollama pull qwen2.5:7b` | digest == `845dbda0ea48…697e` if pulled | old models intact | ENG | PLANNED |
| Model digests | GENERATE | recorded §1 | acceptance record | compare `/api/tags` digests | `bge-m3` **must** match; others recorded | baseline in this doc | ENG | PLANNED |

### 3.6 Secrets and authentication

**No secret value appears in this document, and none may be committed.**

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| `.env` (runtime) | **GENERATE** | `/opt/ai-site-agent/.env` (`home:home` **600**, 25 lines) | same, **600** | recreate from `.env.example`; **rotate DB password** | mode 600; backend starts; `DATABASE_URL` resolves | old `.env` intact | OPS | PLANNED |
| `.env` (dev checkout) | GENERATE | repo `.env` (mode **644**) | same, **600** | recreate | mode 600 | old file intact | OPS | PLANNED |
| `STAGING_ADMIN_PASSWORD` | **GENERATE** | `deploy.local.conf` (mode **644** — world-readable) | same file at **600** | new value | `smoke` `POST /api/auth/login` = 200 | old value intact | OPS | PLANNED |
| SSH keys | **GENERATE** | **none** (`~/.ssh` absent, 0 host keys) | new keypair | `ssh-keygen -t ed25519`; **key-only auth, password auth disabled** | `ssh -T` succeeds; `PasswordAuthentication no` | N/A | OPS | PLANNED |
| `openssh-server` | REINSTALL | **not installed on old host** | **new host only** | `apt install openssh-server` | `systemctl is-active ssh`; key-only | old host stays without sshd | OPS | PLANNED |
| GitHub authentication | **GENERATE** | HTTPS, **no helper, no `gh`, no key** → interactive-only | SSH deploy key | new key registered to the account/repo | `git fetch` + `git push --dry-run` non-interactive | old host unchanged | ENG | PLANNED |
| git identity | GENERATE | **unset** — commits attributed `root@DESKTOP-I2KQV1N` | explicit name/email | `git config` | `git log -1 --format='%an <%ae>'` meaningful | — | ENG | PLANNED |

### 3.7 Cursor and agent tooling

| Component | Class | Current location | Target location | Transfer method | Verification | Rollback | Owner | Status |
|-----------|-------|------------------|-----------------|-----------------|--------------|----------|-------|--------|
| Cursor (application) | REINSTALL | Cursor desktop + WSL remote | new host | fresh install | Cursor connects; opens repo | old install intact | OPS | PLANNED |
| `.cursor-server` | **SKIP** | `/home/home/.cursor-server` (**738 MB**) | — | **never copy** — build-hash-keyed, regenerated on first connect | regenerates automatically | N/A | OPS | PLANNED |
| Cursor settings | GENERATE | `/home/home/.cursor` (37 MB) | new host | reconfigure; **do not copy** `ide_state.json` / `projects` (host-specific session state) | Cursor usable | old settings intact | OPS | PLANNED |
| Cursor extensions | REINSTALL | Cursor user data | new host | reinstall from Cursor | extensions listed | — | OPS | PLANNED |
| `.cursor/` (repo) | REBUILD | `<repo>/.cursor` (20 KB) | same | **arrives with the clone — in git** | directory present after clone | — | ENG | PLANNED |
| `.cursor/rules` | REBUILD | 3 `.mdc` files, **version-controlled** | same | **arrives with the clone** | `release-engineering-workflow.mdc`, `knowledge-intelligence-manifest.mdc`, `knowledge-os-development-charter.mdc` present | — | ENG | PLANNED |
| Cursor MCP / connectors | **SKIP** | **no `mcp.json`** at user or repo scope | — | nothing to migrate | absence confirmed | N/A | ENG | PLANNED |
| Terminal profiles | **SKIP** | not separately configured | — | nothing to migrate | N/A | N/A | OPS | PLANNED |
| Cursor skills | REINSTALL | `/home/home/.cursor/skills-cursor` (user scope) | new host | re-provision at user level | skills available | old intact | OPS | PLANNED |
| Project instructions | **SKIP** | **no `AGENTS.md`** in repo | — | nothing to migrate | absence confirmed | N/A | ENG | PLANNED |

### 3.8 Classification summary

| Class | Count | Components |
|-------|-------|------------|
| **RESTORE** | 2 | `ai_site_agent`, Qdrant `site_knowledge` |
| **COPY** | 2 | curated backups, logs archive |
| **REBUILD** | 9 | repo, `deploy/`, `manage_deploy.sh`, `/opt` layout, venv, build artifacts, backend, repo `.cursor`, `.cursor/rules` |
| **REINSTALL** | 12 | OS, apt packages, Python, Node, PG cluster, Qdrant, Ollama runtime, `ollama.service`, `openssh-server`, Cursor application, Cursor extensions, Cursor skills |
| **RE-PULL** | 3 | `bge-m3`, `qwen2.5:3b`, `qwen2.5:7b` (deferred) |
| **GENERATE** | 26 | locale/collation, timezone, users/groups, firewall, logrotate, permissions, `origin` URL, `deploy.local.conf`, systemd units, nginx config, `ai_agent` role, answer-cache collection, service binds ×4 (PG, Qdrant, Ollama, nginx), addressing, hostname, digests record, `.env` ×2, `STAGING_ADMIN_PASSWORD`, SSH keys, GitHub auth, git identity, Cursor settings |
| **SKIP** | 7 | `ai_site_agent_recovery`, certificates, cron, `.cursor-server`, MCP, terminal profiles, `AGENTS.md` |
| **TOTAL** | **61** | must equal the number of classified rows in §3.1–§3.7 |

The total is an invariant, not a description: if the sum of the counts above does not equal the
number of manifest rows, a component has been added or dropped without classification and this table
is no longer a completeness proof.

**Only two components are RESTORE.** That is the whole irreducible risk surface of this migration —
everything else is reproducible from source, packages, or registries.

---

## 4. Dependency graph

Solid arrows are hard ordering constraints. Each annotation states *why* the edge cannot be
reordered.

```text
                    ┌──────────────────────────────────┐
                    │ OS install (Ubuntu 24.04 LTS)    │
                    │ systemd = PID 1  [MANDATORY]     │
                    └────────────────┬─────────────────┘
                                     ↓
                    ┌──────────────────────────────────┐
                    │ apt packages                     │
                    │ PG16 · nginx · git · rsync ·      │
                    │ build-essential · openssh-server │
                    └────────────────┬─────────────────┘
                                     ↓
        ┌────────────────────────────┴───────────────────────────┐
        ↓                                                        ↓
┌──────────────────────────┐                    ┌────────────────────────────┐
│ Locale C.UTF-8 +         │                    │ Users / groups             │
│ timezone                 │                    │ APP_USER · postgres ·      │
│ ★ BEFORE initdb —        │                    │ qdrant · ollama            │
│   collation is immutable │                    │ ★ must match unit User=    │
└────────────┬─────────────┘                    └──────────┬─────────────────┘
             │                                             │
             │              ┌──────────────────────────────┴───────────┐
             │              ↓                                          ↓
             │   ┌────────────────────┐                   ┌─────────────────────────┐
             │   │ Python 3.12        │                   │ Node 20.20.2 via nvm    │
             │   │ (system)           │                   │ ★ AS APP_USER — nvm is  │
             │   └─────────┬──────────┘                   │   user-scoped; sudo     │
             │             │                              │   drops it from PATH    │
             │             │                              └───────────┬─────────────┘
             │             └──────────────┬───────────────────────────┘
             │                            ↓
             │              ┌──────────────────────────────┐
             │              │ SSH keypair (ed25519)        │
             │              │ + GitHub auth                │
             │              │ ★ BEFORE clone — no helper   │
             │              │   exists today               │
             │              └──────────────┬───────────────┘
             │                             ↓
             │              ┌──────────────────────────────┐
             │              │ Clean clone origin/main      │
             │              │ main @ C_cut [not detached]  │
             │              └──────────────┬───────────────┘
             │                             ↓
             │              ┌──────────────────────────────┐
             │              │ Secrets: .env (600) +        │
             │              │ deploy.local.conf (600)      │
             │              │ ★ GENERATE + ROTATE          │
             │              │ ★ NPM_BIN/NODE_BIN must      │
             │              │   match real Node paths      │
             │              └──────────────┬───────────────┘
             │                             │
             └──────────────┬──────────────┘
                            ↓
   ┌────────────────────────┼────────────────────────┬──────────────────┐
   ↓                        ↓                        ↓                  ↓
┌───────────────┐   ┌────────────────┐   ┌──────────────────┐   ┌─────────────┐
│ PostgreSQL    │   │ Qdrant 1.12.4  │   │ Ollama 0.30.10   │   │ nginx 1.24  │
│ initdb C.UTF-8│   │ binary+config  │   │ RE-PULL models   │   │ site config │
│ CREATE ROLE   │   │ LimitNOFILE    │   │ bge-m3 digest ★  │   │ 300s proxy  │
│ ai_agent      │   │ =65536         │   │ qwen2.5:3b       │   │ 20m body    │
└───────┬───────┘   └────────┬───────┘   └────────┬─────────┘   └──────┬──────┘
        │                    │                    │                    │
        │  ══════════════════╪════════════════════╪════════════════════╪═══════
        │  ║  FREEZE OLD HOST — stop ai-agent-backend.service          ║
        │  ║  sole writer to BOTH Postgres and Qdrant                  ║
        │  ══════════════════╪════════════════════╪════════════════════╪═══════
        ↓                    ↓                    │                    │
┌───────────────┐   ┌────────────────┐            │                    │
│ pg_restore    │   │ snapshot       │            │                    │
│ ai_site_agent │   │ restore        │            │                    │
└───────┬───────┘   └────────┬───────┘            │                    │
        └─────────┬──────────┘                    │                    │
                  ↓                               │                    │
   ┌──────────────────────────────────┐            │                    │
   │ ★ ATOMIC PAIR VERIFICATION       │            │                    │
   │ chunks 17958 ↔ points 18780      │            │                    │
   │ knowledge_version = 26           │            │                    │
   │ same frozen instant — no skew    │            │                    │
   └──────────────┬───────────────────┘            │                    │
                  │                                │                    │
                  │   ┌────────────────────────────┘                    │
                  ↓   ↓                                                 │
   ┌──────────────────────────────────┐                                 │
   │ ★ bge-m3 digest verified BEFORE  │                                 │
   │   first retrieval — else silent  │                                 │
   │   embedding degradation          │                                 │
   └──────────────┬───────────────────┘                                 │
                  ↓                                                     │
   ┌──────────────────────────────────┐                                 │
   │ systemd units                    │                                 │
   │ qdrant + ollama → THEN backend   │←────────────────────────────────┘
   │ (After= / Wants= ordering)       │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ deploy full                      │
   │ backup→build→sync→verify→        │
   │ restart→smoke                    │
   │ ★ requires clean tree AND        │
   │   main == origin/main (git fetch)│
   │ ★ internal Alembic = NO-OP @0019 │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ health → build-info → smoke →    │
   │ verify-release                   │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ Manual validation (§6 T+35)      │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ ACCEPTANCE (§7 A1–A42)           │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ Hostname / access switch         │
   │ ★ ONLY after acceptance          │
   └──────────────┬───────────────────┘
                  ↓
   ┌──────────────────────────────────┐
   │ Rollback window: old host FROZEN │
   │ acceptance + 14 days             │
   └──────────────────────────────────┘
```

### The six edges that cannot be reordered

| Edge | Why | Failure if violated |
|------|-----|--------------------|
| Locale → `initdb` | collation fixed at cluster/DB creation | `pg_restore` **succeeds** but text ordering silently differs |
| Node as APP_USER → `deploy full` | nvm is user-scoped; `sudo` drops it from `PATH` | build stage fails *after* the backup |
| GitHub auth → clone on `main` → `deploy full` | `deploy full` deploys the `origin/main` tip and refuses detached/non-`main`/dirty trees; `verify-release` requires `main == origin/main` (§6.1) | deploy **refused**, or validation gate unreachable |
| `deploy full` → start `ai-agent-backend` | the unit's `ExecStart` is `/opt/…/.venv/bin/python`, which `deploy full` creates | unit fails into a `Restart=on-failure` loop |
| Freeze → capture(PG **and** Qdrant) | backend is the sole writer to both | version skew; silent retrieval corruption |
| `bge-m3` digest verify → first retrieval | 18780 vectors are this model's output | silent quality degradation, no error |

---

## 5. Downtime window derivation

Pre-staging removes everything immutable from the window. Only the ~250 MB atomic pair moves inside
it.

| Step | Estimate | Evidence |
|------|----------|----------|
| Stop backend | 5 s | Gate D log: `Backend stopped` |
| `backup db` (`pg_dump -Fc`) | ~15 s | Gate D stage 1 within a 48 s total deploy |
| Qdrant snapshots (both) | ~20 s | 143 MB storage |
| Checksums | ~5 s | 11.6 MB + snapshots |
| Transfer (~250 MB) | ~60 s | LAN-dependent |
| `pg_restore` | ~45 s | 103 MB logical |
| Qdrant snapshot restore | ~30 s | 18780 points |
| Data verification | ~2 min | counts + versions + flags |
| `deploy full` | **48 s** | **measured** 2026-07-29 |
| `health`/`build-info`/`smoke`/`verify-release` | ~3 min | smoke includes 41 golden tests |
| Manual validation | ~10 min | chat, follow-up, dashboard |
| **Technical subtotal** | **≈ 18–20 min** | |
| Contingency (1×) | +20 min | |
| **Proposed approved window** | **60 min** | 30 min technical target |

The dominant cost is **verification, not data movement** — the correct shape for a migration whose
irreplaceable payload is 250 MB.

---

## 6. Cutover plan

`T` = freeze start. Everything before `T` is reversible with zero impact; the old host keeps serving
until `T`.

### Pre-cutover (days before — no downtime, no impact)

| When | Action | Gate |
|------|--------|------|
| D-3 | Provision host; confirm every §2 fact-sheet row | **STOP** if any blocker row fails |
| D-3 | Install OS, apt packages; set **locale `C.UTF-8`** and timezone | `locale` correct **before** `initdb` |
| D-3 | Create users/groups; install Python 3.12; install Node 20.20.2 **as APP_USER** | `node -v`; path matches planned `NODE_BIN` |
| D-2 | `initdb` with `C.UTF-8`; `CREATE ROLE ai_agent` (rotated password) | `SHOW lc_collate` = `C.UTF-8` |
| D-2 | Install Qdrant 1.12.4 + `config.yaml` (loopback, `LimitNOFILE=65536`) | `GET /` = 1.12.4 |
| D-2 | Install Ollama; **`ollama pull bge-m3 qwen2.5:3b`**; `qwen2.5:7b` only if GPU | **`bge-m3` digest == `7907646426…6bab`** — else COPY blob |
| D-2 | Generate SSH keys; register GitHub auth; set git identity | `git fetch` + `push --dry-run` non-interactive |
| D-2 | Clean `git clone`; stay on **`main` tracking `origin/main`** — **never** a detached checkout of a literal hash; create `.env` + `deploy.local.conf` at **600** | `git status --porcelain` empty; `git rev-parse --abbrev-ref HEAD` = `main`; `main` == `origin/main` |
| D-2 | **Record the cutover commit `C_cut` = `git rev-parse origin/main`.** This — not a historical hash — is the identity every criterion asserts | `C_cut` written into the cutover record |
| D-2 | **Declare a merge freeze on `main`** from now until acceptance (see §6.1) | no new commits on `origin/main` during the window |
| D-1 | Configure nginx, systemd units, `ufw`, logrotate | `nginx -t`; unit ordering correct |
| D-1 | **Dry run** `bash deploy/manage_deploy.sh doctor` and `status` | both pass |
| D-1 | Record old-host baseline: counts, versions, digests, ports | matches this manifest |
| D-1 | Go/no-go review | **STOP** on any unmet gate |

### Cutover window

| Time | Action | Verification | Rollback if failed |
|------|--------|--------------|--------------------|
| **T-5** | Announce freeze; confirm no `index_jobs` running | `health` → `index_job_status=completed` | abort, no impact |
| **T+0** | **FREEZE.** `systemctl stop ai-agent-backend` on **old** host | `is-active` = inactive; **writes to PG and Qdrant now impossible** | restart backend — full rollback, zero loss |
| **T+1** | `bash deploy/manage_deploy.sh backup db` on old host | dump created; SHA256 recorded | restart backend |
| **T+2** | Snapshot **both** Qdrant collections (same frozen instant) | snapshot files + SHA256 | restart backend |
| **T+3** | `pg_restore --list` the dump | 217 TOC / 19 TABLE DATA / `public.settings` | **STOP** — do not proceed on a bad dump |
| **T+4** | Transfer dump + snapshots to new host | SHA256 re-verified on arrival | restart old backend |
| **T+5** | `createdb ai_site_agent` owned by `ai_agent` (role already exists from D-2) | `\l` shows the empty DB, `lc_collate=C.UTF-8` | restart old backend |
| **T+6** | `pg_restore` into empty `ai_site_agent` | exit 0, no errors | restart old backend |
| **T+8** | Verify schema: `alembic_version` = `0019_legacy_doc_type_canonical_enabled` | exact match | restart old backend |
| **T+9** | Verify data: 5023 / 17958 / 39 / 13 / 21; `kv=26`, `mv=177`; 11 flags **false** | all exact | restart old backend |
| **T+11** | Restore Qdrant `site_knowledge`; create answer-cache empty (1024/Cosine) | 18780 pts, `green`, 1024/Cosine | restart old backend |
| **T+13** | **Atomic-pair check:** chunks 17958 ↔ points 18780 ↔ `kv=26` | consistent | restart old backend |
| **T+14** | **Verify `bge-m3` digest** and `embedding_length=1024` | digest match | **STOP** — COPY blob from old host |
| **T+15** | Start `qdrant` and `ollama` **only**. **Do not start `ai-agent-backend` yet** — its `ExecStart` is `/opt/ai-site-agent/backend/.venv/bin/python`, which does not exist until `deploy full` builds it; starting it here yields a `Restart=on-failure` loop | both active; backend still inactive | restart old backend |
| **T+16** | `git fetch`; confirm `origin/main` **still == `C_cut`**, `main` == `origin/main`, tree clean, **not detached** | exact match | **STOP** — `main` moved; re-baseline `C_cut` before deploying |
| **T+17** | `sudo bash deploy/manage_deploy.sh deploy full` — this bootstraps `/opt`, creates the venv, installs deps, builds the frontend, and **starts the backend at stage 3** | 6/6 stages; **internal Alembic = no-op**, zero `Running upgrade` lines; backend now active | restart old backend |
| **T+19** | `health` · `build-info` | `database=0019…`; identity == **`C_cut`**; release 0.8 | restart old backend |
| **T+21** | `smoke` | 6 HTTP checks + **41** golden tests (note: golden tests are **offline unit tests** — they are not a retrieval-quality gate) | restart old backend |
| **T+23** | `verify-release` | **FULL CHAIN ALIGNED**, `FAIL=0` — valid **only while `origin/main` == `C_cut`** (§6.1) | restart old backend |
| **T+25** | `ss -lntup`; `ufw status`; `stat .env` | matches §3.4; `.env` = 600 | restart old backend |
| **T+27** | Manual: dashboard, deep link, chat, follow-up, sources | grounded answers | restart old backend |
| **T+35** | Confirm no unintended writes: claims still 39; no new `index_jobs` | exact | restart old backend |
| **T+40** | **ACCEPTANCE REVIEW** — A1–A42 | all PASS | **ROLLBACK POINT** — last clean abort |
| **T+45** | Hostname / access switch to new host | new host serves | rollback per §8 |
| **T+50** | Old host confirmed **frozen** (backend stays stopped) | `is-active` = inactive | — |
| **T+60** | Window closes; rollback window opens (14 days) | recorded | §8 |

**The rollback point is T+40.** Before it, rollback is "restart the old backend" with zero data
loss, because the old host was never mutated. After it, §8 applies and any writes accepted by the
new host are **discarded** — there is no merge path.

### 6.1 Deployed identity is `origin/main`, not a pinned hash

This constraint comes from the tooling, not from preference, and it governs every identity criterion
in §7:

| Fact | Evidence |
|------|----------|
| `deploy full` deploys the **`origin/main` tip**. There is no `--commit` flag | `deploy/lib/deploy_source.sh` |
| A detached checkout of a literal hash is **refused** | `deploy_guard`: `ERROR: not on main branch (HEAD=detached)` |
| A non-`main` branch and a dirty tree are **refused** | `deploy_guard` |
| `verify-release` compares build-info, frontend identity, and `/api/build` against **`origin/main`** — a moving reference, not a pinned release commit | `scripts/release/verify-release.sh` |

Two consequences the operator must internalise:

1. **The cutover deploys `C_cut`, the `origin/main` tip recorded at D-2** — not a historical release
   hash. Acceptance asserts `C_cut`. Re-confirm it at T+16, and hold the merge freeze so it cannot
   move mid-window.
2. **A documentation-only commit on `main` makes `verify-release` report identity FAIL on an
   already-correct host,** because the deployed commit no longer equals the `origin/main` tip. The
   runtime is unchanged; only the reference moved. This is expected, and it is why the merge freeze
   exists.

**Operator safety note for rollback:** the old host is deployed at
`39ebef1b76a4236a8e608d7300cbecf0107f75b4`. Whenever `main` is ahead of that commit, a rollback to
the old host will show a `verify-release` **identity mismatch that is not a rollback failure**. Do
not treat it as one, and do not "fix" it by deploying. The authoritative rollback proof is `health`,
`build-info`, the data counts, and the Alembic revision — see §8 step 5.

---

## 7. Acceptance criteria

Every criterion is a command with an exact expected value. A1–A22 carry over from Part 1; A23–A42
are new. No subjective wording.

### Identity and schema

| # | Criterion | Measurement | Expected |
|---|-----------|-------------|----------|
| A1 | Release verification | `verify-release` | **PASS**, `FAIL=0` — requires the §6.1 merge freeze to be intact |
| A2 | Identity chain | `verify-release` | `origin/main` == build-info == frontend == `/api/build`, all == `C_cut` |
| A3 | Release | `/api/build` `.release` | `0.8` |
| A4 | Alembic head | `/api/build` `.alembic_head` | `0019_legacy_doc_type_canonical_enabled` |
| A5 | Health | `/api/health` | `app`,`ollama`,`qdrant`,`database` all `ok` |
| A6 | Code provenance | deploy log | clean `origin/main` worktree; **no** dirty-tree copy |
| A23 | Deployed commit | `.build-info.json` `.git_commit` | **`C_cut`** — the `origin/main` tip recorded at D-2 and re-confirmed at T+16 (§6.1). Not a historical hash |
| A24 | Internal Alembic no-op | deploy log stage 3 | **zero** `Running upgrade` lines |

### Data integrity

| # | Criterion | Measurement | Expected |
|---|-----------|-------------|----------|
| A7 | sources / chunks | SQL count | **5023** / **17958** |
| A8 | claims / observations / links | SQL count | **39** / **13** / **21** |
| A9 | knowledge / memory version | `settings` id 1 | **26** / **177** |
| A10 | Qdrant `site_knowledge` | `GET /collections/site_knowledge` | **18780** points, `green` |
| A11 | Vector config | same | size **1024**, distance **Cosine** |
| A12 | `bge-m3` digest | `/api/tags` | **`7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`** |
| A25 | `qwen2.5:3b` digest | `/api/tags` | `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` |
| A26 | Embedding length | `/api/show bge-m3` | `bert.embedding_length` = **1024** |
| A27 | DB collation | `SHOW lc_collate` | **`C.UTF-8`** |
| A28 | DB encoding | `pg_encoding_to_char` | **`UTF8`** |
| A29 | PG server version | `SHOW server_version` | **≥ 16** |
| A30 | Settings row 2 | SQL | `kv=20`, `mv=10`, unchanged |
| A31 | Recovery DB absent | `\l` | **no** `ai_site_agent_recovery` |
| A32 | Answer-cache collection | `GET /collections/...answer_cache` | exists, `green`, **1024/Cosine** |

### Configuration and flags

| # | Criterion | Measurement | Expected |
|---|-----------|-------------|----------|
| A13 | Experimental flags | `/api/build` `.feature_flags` | all **11 false** |
| A14 | 0.8 flag DDL | `information_schema.columns` | both `default false`, `NOT NULL` |
| A15 | Lifecycle | `/api/build` `.release_status` | `staging_validated=false`, `production_ready=false` |
| A16 | Listening ports | `ss -lntup` | only nginx `:80` non-loopback; 8000/5432/6333/6334/11434 loopback |
| A17 | Ownership | `stat` | consistent per W1; **`.env` = 600** |
| A33 | Firewall | `ufw status` | **active**, default deny inbound |
| A34 | No exposed data ports | `ss -lntup` | 5432/6333/6334/11434 **never** `0.0.0.0` |
| A35 | Unit ordering | `systemctl cat ai-agent-backend` | `After=` includes `qdrant.service` + `ollama.service` |
| A36 | Qdrant file limit | `systemctl cat qdrant` | `LimitNOFILE=65536` |
| A37 | Ollama unit hygiene | `systemctl cat ollama` | PATH contains **no** `/mnt/c` and no `.cursor-server` |
| A38 | nginx behaviour | `nginx -T` | `proxy_read_timeout 300s`; `client_max_body_size 20m`; SPA `try_files` |
| A39 | SSH hardening | `sshd -T` | `passwordauthentication no` |
| A40 | Git non-interactive | `git fetch && git push --dry-run` | both succeed without prompting |
| A41 | logrotate present | `logrotate --debug` | `/etc/logrotate.d/ai-site-agent` parses |
| A42 | Disk headroom | `df -h /` | ≥ 50 GB available after migration |

### Functional

| # | Criterion | Measurement | Expected |
|---|-----------|-------------|----------|
| A18 | Smoke | `smoke` | pass — 6 HTTP checks |
| A19 | Golden parity | `smoke` | **41 passed**, 0 failed |
| A20 | Dashboard | browser | loads; deep link resolves (no 404) |
| A21 | Chat + follow-up | `POST /api/chat` | non-empty `answer`, `used_context=true`, ≥ 1 source |
| A22 | No unintended writes | SQL | claims **39**; no new `index_jobs` row |

### Explicit non-criteria

| Item | Why it is not a gate |
|------|---------------------|
| Response-time parity with old host | new hardware invalidates the baseline; measure and record only |
| `staging_validated = true` | machine migration is **not** staging validation |
| `production_ready = true` | gated behind Staging Validated |
| Step 055 overview/news quality | pre-existing; must not block **or** excuse the migration |
| Russian intent classification (`DEBT-0.8-001`) | pre-existing; same reasoning |
| `health` unit-state readout (`DEBT-0.8-002`) | known false negative without privilege |

---

## 8. Risk matrix

Ranked by severity. "Silent" risks rank above loud ones: a failure that surfaces as an error is
cheaper than one that degrades quality without complaint.

| Rank | Risk | Severity | Detection | Mitigation |
|------|------|----------|-----------|------------|
| 1 | **Embedding digest mismatch** — re-pulled `bge-m3` differs; 18780 vectors become inconsistent with new queries | **CRITICAL — silent** | **none at runtime**; only digest comparison | A12/A26 gate at **T+14**; COPY blob if mismatched; digest recorded §1 |
| 2 | **Floating Ollama tags** — `:latest` resolves to a new build at any time | **CRITICAL — silent** | digest comparison only | pin by digest, never by tag; A12/A25 |
| 3 | **Split-brain / dual-write** — both hosts accept writes | **CRITICAL** | divergent counts | single-writer invariant; old host stays frozen (§9); no dual-write mode exists |
| 4 | **PG/Qdrant version skew** — captured at different instants | **HIGH — silent** | atomic-pair check | capture both from one frozen instant; A7/A10/A9 at T+13 |
| 5 | **Database compatibility — collation** | **HIGH — silent** | `SHOW lc_collate` | locale **before** `initdb`; A27/A28 |
| 6 | **Database compatibility — major version** | **HIGH — loud** | `pg_restore` fails | mandate PG ≥ 16; A29 |
| 7 | **Old host mutated during rollback window** | **HIGH** | audit | K1–K3; keep backend stopped; A-window discipline |
| 8 | **Qdrant compatibility** — snapshot format across versions | **HIGH — loud** | restore fails | mandate 1.12.4; verify `GET /` before window |
| 9 | **Permissions** — `.env` mode, data dirs, `deployments` `root:root` drift | **HIGH** | `stat` | A17/A33; W1–W5; `.env` 600 at creation |
| 10 | **APP_USER mismatch** — `deploy.local.conf` vs unit `User=` vs `/opt` owner | **MEDIUM — delayed** | fails on the *next* deploy | single user decided once; A17/A35; heed the `www-data` warning |
| 11 | **Node path portability** — absolute nvm `NPM_BIN`/`NODE_BIN` | **MEDIUM — loud** | `deploy full` build stage fails after backup | install Node as APP_USER at same path, or update both keys; D-3 gate |
| 12 | **systemd** — not PID 1, or wrong unit ordering | **MEDIUM** | backend starts before deps | mandate PID 1; A35/A36; U3–U5 |
| 13 | **Firewall** — none today; WSL2 isolation not portable | **MEDIUM** | `ss` / `ufw status` | `ufw` default deny; A33/A34; internet exposure = separate work |
| 14 | **GPU compatibility** — driver/VRAM mismatch, or absent | **MEDIUM** | `ollama` load failure or slowness | GPU optional; skip `qwen2.5:7b` without GPU; performance is a non-criterion |
| 15 | **Disk space** — models + backups + artifacts | **MEDIUM** | `df` | mandate 100 GB; A42; curate backups (B1) |
| 16 | **Missing `.env` not failing startup** (`EnvironmentFile=-`) | **MEDIUM** | confusing runtime errors | verify `.env` explicitly at T+25; do not rely on the unit |
| 17 | **`ai_site_agent_recovery` mistaken for live** | **MEDIUM** | wrong `DATABASE_URL` | SKIP; A31 asserts absence |
| 18 | **Secrets exposure in transit** | **MEDIUM** | — | GENERATE + rotate; never copy; `deploy.local.conf` at 600 |
| 19 | **Interactive-only git auth** blocks `verify-release` | **MEDIUM — loud** | `git fetch` prompts | SSH key at D-2; A40 |
| 20 | **Stale flat backups copied** (809 MB / 51 dumps) | LOW | `du` | curate: 3 dumps + `releases/0.7/` |
| 21 | **Reduced RAM** vs 7.7 GiB baseline | LOW | OOM / slowness | mandate ≥ 16 GB |
| 22 | **`CORS_ORIGINS` still lists Vite dev ports** in `APP_ENV=production` | LOW | — | recorded observation; **no fix in scope** |

---

## 9. Rollback

**Invariant: exactly one host is authoritative at every instant. No dual-write. No split-brain. No
partial ownership.**

### Why rollback is cheap before T+40

The old host is never mutated during the cutover. It is stopped, read, and left alone. Rollback
before the acceptance gate is therefore **not a restore** — it is starting a service.

### Rollback before T+40

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Stop **all** services on the new host — `ai-agent-backend`, then `qdrant`, `ollama` | `is-active` = inactive for all |
| 2 | Confirm the new host cannot accept traffic | port 80 closed or nginx stopped |
| 3 | `systemctl start ai-agent-backend` on the **old** host | `is-active` = active |
| 4 | `bash deploy/manage_deploy.sh health` | `app`/`ollama`/`qdrant`/`database` = `ok` |
| 5 | `bash deploy/manage_deploy.sh verify-release` | Deployed commit == `39ebef1`. **If `main` is ahead of `39ebef1`, the identity checks report FAIL — that is expected drift, not a rollback failure (§6.1).** Rollback proof is steps 4, 6, and 7; never "fix" this by deploying |
| 6 | Confirm data unchanged | 5023 / 17958 / 39 / 13 / 21; `kv=26`, `mv=177`; Qdrant 18780 |
| 7 | Confirm Alembic | `0019_legacy_doc_type_canonical_enabled` |
| 8 | Record the rollback and the reason | written record |

**Data loss: zero.** No write reached the new host because it never served traffic.

### Rollback after T+45 (access already switched)

| Step | Action | Note |
|------|--------|------|
| 1 | Stop new-host backend **first** | prevents any further divergence — do this before anything else |
| 2 | Enumerate writes the new host accepted | `chat_messages`, `answer_traces`, `index_jobs`, claims |
| 3 | **Discard them** | **there is no merge path**; the corpus and Memory have no conflict resolution |
| 4 | Restart old-host backend | old host resumes as sole authority |
| 5 | Revert hostname / access | old host reachable |
| 6 | Full verification | steps 4–8 above |
| 7 | Record discarded writes explicitly | audit trail |

**This is why access must not switch before acceptance.** Any write after T+45 is lost on rollback.

### Rollback window rules

| # | Rule |
|---|------|
| K1 | Do **not** decommission, wipe, or upgrade the old host until acceptance **+ 14 days** |
| K2 | Do **not** delete `/opt/ai-site-agent/backups` on the old host — it is rollback material |
| K3 | Keep the old host **frozen** (backend stopped) for the whole window — never let it resume writing |
| K4 | Rollback = start the old backend; **no restore required** |
| K5 | Never "fix" a rollback by clearing Qdrant or re-running indexing |
| K6 | Record which host is authoritative at every moment |
| K7 | Writes accepted by the new host before rollback are **discarded** |
| K8 | Window closes only on a written acceptance record after 14 days of normal operation |

### Forbidden "fixes"

| Action | Why forbidden |
|--------|--------------|
| Clear/recreate `site_knowledge` | 18780-point re-embed is long, CPU-bound, and changes retrieval results |
| Run indexing to "repair" a bad restore | masks the restore failure; mutates the corpus |
| `alembic upgrade` instead of restoring | schema must arrive with its data |
| Run both hosts writable "briefly" | unreconcilable divergence |
| Copy the dev checkout into `/opt` | violates clean-`origin/main` provenance |
| Re-point new host at the old host's database | dual ownership of one dataset |

---

## 10. Non-goals

Explicitly out of scope. Presence in this document is not authorization.

| Non-goal | Statement |
|----------|-----------|
| **Release 0.9** | **No Release 0.9.** Blocked until machine-migration acceptance is recorded. |
| **Architecture redesign** | **No architecture redesign.** This migration reproduces the current architecture on new hardware. |
| **Memory changes** | **No Memory changes.** Epistemic Memory code, schema, and flags are untouched; `memory_shadow_write_enabled` stays `false`. |
| **Reasoning changes** | **No Reasoning changes.** `REASONING_SERVICE_ENABLED` and all related flags stay `false`. |
| **Step 055 quality fixes** | **No Step 055 quality fixes.** `legacy_doc_type_canonical_enabled` stays `false`; the confirmed news-in-overview risk is not addressed here. |
| **Russian query fixes** | **No Russian query fixes.** `DEBT-0.8-001` stays deferred. |
| **Feature work** | **No feature work.** No new endpoints, flags, models, or capabilities. |
| Flag changes | No flag is enabled. All 11 stay `false`. |
| Settings changes | No Settings value is modified. |
| Lifecycle promotion | `staging_validated` and `production_ready` stay `false`. |
| Reindex | No reindex, re-embed, or corpus mutation. |
| TLS / internet exposure | Deferred — separate scoped review. |
| `DEBT-0.8-002` | `health` privilege reporting stays deferred. |
| Retention implementation | Policy is *proposed* here; implementing pruning automation is separate work. |

---

## 11. Remaining required user inputs

Everything else is resolved. These are values and approvals, not investigations.

| # | Input | Blocks | Default if unspecified |
|---|-------|--------|----------------------|
| 1 | **Confirmed §2 fact sheet** for the actual machine | D-3 go/no-go | — none; hard blocker |
| 2 | **Final runtime hostname** | §3.4 | — none |
| 3 | Approve **60-minute** window and schedule `T` | §6 | — none |
| 4 | Confirm **local-only** exposure (item 10) | TLS/firewall scope | proceed local-only |
| 5 | Confirm **static IP / DHCP reservation** | §3.4 | DHCP acceptable local-only |
| 6 | Approve **secret rotation** (DB password + `STAGING_ADMIN_PASSWORD`) | §3.6 | proceed with rotation |
| 7 | Approve **SSH key-only** auth + `openssh-server` on new host | §3.6 | proceed |
| 8 | Approve **GitHub SSH deploy key** | §3.6 | proceed |
| 9 | Confirm `ai_site_agent_recovery` **archive-and-skip** | §3.3 | proceed with SKIP |
| 10 | Approve retention: **14 daily + 4 weekly + release-tagged** | §3.1 | proceed |
| 11 | Approve rollback window: **acceptance + 14 days** | §9 | proceed |
| 12 | Named **OPS** and **ENG** owners | manifest Owner column | — none |
| 13 | Named **cutover approver** | T+40 gate | — none |
| 14 | Approve GPU branch: pull `qwen2.5:7b` only if GPU present | §3.5 | skip 7B |

---

## 12. Review status

| Gate | State |
|------|-------|
| Part 1 — old-machine baseline | **complete** |
| Part 2 — manifest, graph, cutover, acceptance, risks, rollback | **complete, awaiting review** |
| All 20 unknowns | **resolved** (14 measured, 6 proposed decisions) |
| Architecture review approval | **NOT GRANTED** |
| Migration execution | **NOT AUTHORIZED** |
| Old host | **remains sole authoritative runtime, untouched** |
| Release 0.9 | **blocked** |

**Nothing was executed, deployed, restored, copied, or cut over to produce this document.** All
findings are read-only measurements taken 2026-07-29.

---

## Sign-off

| Role | Name | Date |
|------|------|------|
| OPS owner | | |
| ENG owner | | |
| Architecture review approver | | |
| Cutover approver | | |
| Migration acceptance | | |
