# AI Site Agent

A **local AI website knowledge agent** with an admin dashboard, running entirely
on your own Linux server. It indexes a website (pages + downloadable files),
stores the content in a local knowledge base, and answers questions **only from
the indexed content** using a **local LLM**. If the answer is not present in the
indexed knowledge, it returns a fixed fallback answer and **never hallucinates**.

- **No cloud. No OpenAI/Anthropic. No Docker.**
- LLM + embeddings run locally via **Ollama**.
- Vectors stored locally in **Qdrant** (installed as a native binary).
- App metadata in **PostgreSQL** (the only supported database engine).
- Backend: **FastAPI + SQLAlchemy + Alembic + Pydantic**. Dashboard: **React + TypeScript + Vite**.
- Deployment: Python venv + Node build + **systemd** + **Nginx**.

---

## What it does

1. Index a website by **sitemap** and/or **crawling** from a start URL.
2. Optionally discover and index **downloadable files** (PDF, DOCX, TXT) — see
   [How to use indexing](#how-to-use-indexing) for scan modes and the file toggle.
3. Clean extracted text, **chunk** it, embed it locally, and store vectors in Qdrant.
4. Answer questions with a **grounded RAG** flow over the indexed content.
5. **Refuse to hallucinate**: if retrieval finds nothing above the similarity
   threshold, the LLM is **not** called and the agent returns:
   > Я не знайшов цієї інформації на сайті.
6. Provide an **admin dashboard** for indexing, settings, sources, logs and a chat test page.

### No-hallucination guarantee

The chat endpoint always:
1. embeds the question locally,
2. searches Qdrant for the top-K chunks,
3. filters them by the configured **similarity threshold**,
4. if nothing passes → returns the fallback answer **without calling the LLM**,
5. otherwise builds a prompt where retrieved content is clearly delimited as a
   **knowledge source, not instructions** (prompt-injection text inside indexed
   content is ignored).

---

## Requirements

- **Linux** server (Ubuntu/Debian-like assumed in examples)
- **Python 3.11+**
- **Node.js 18+** (to build the dashboard)
- **Ollama** (local LLM + embeddings)
- **Qdrant** (local native binary, no Docker)
- **Nginx** (to serve the dashboard and proxy the API)

---

## Project structure

```text
ai-site-agent/
  backend/        FastAPI knowledge agent service (Python venv)
  dashboard/      React + TS + Vite admin dashboard
  deploy/         systemd units, nginx config, install scripts
  scripts/        dev/run helper scripts
  README.md
  .env.example
```

---

## Local Linux installation (step by step)

All commands assume the repo lives at `/opt/ai-site-agent` (adjust as needed).

### 1. Install Ollama and pull models

```bash
bash deploy/install_ollama.sh
# or manually:
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull bge-m3
```

### 2. Install Qdrant (no Docker)

```bash
sudo bash deploy/install_qdrant.sh
# Installs the binary to /opt/qdrant and writes /opt/qdrant/config.yaml.
```

Run it as a service:

```bash
sudo useradd -r -s /bin/false qdrant || true
sudo chown -R qdrant:qdrant /var/lib/qdrant
sudo cp deploy/systemd/qdrant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now qdrant
```

### 3. Create the Python venv and install the backend

```bash
bash deploy/install_backend.sh
```

This creates `backend/.venv`, installs dependencies and creates `.env` from
`.env.example`. You must provision PostgreSQL and run migrations before starting
the backend — see [PostgreSQL setup](#postgresql-setup) below.

### PostgreSQL setup

The backend is **PostgreSQL-only** and refuses to start without a valid
`DATABASE_URL`. Install and provision PostgreSQL on Ubuntu:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

Create the application role and database:

```sql
CREATE USER ai_agent WITH PASSWORD 'change_me';
CREATE DATABASE ai_site_agent OWNER ai_agent;
GRANT ALL PRIVILEGES ON DATABASE ai_site_agent TO ai_agent;
```

Set the connection string in `.env`:

```env
DATABASE_URL=postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent
```

Apply the schema (Alembic migrations own the schema — there is no runtime
auto-create):

```bash
cd backend && alembic upgrade head
# or: python -m app.scripts.maintenance migrate
```

The deploy script automates these steps:

```bash
bash deploy/manage_deploy.sh --action install-postgres
bash deploy/manage_deploy.sh --action setup-postgres-db
bash deploy/manage_deploy.sh --action run-migrations
bash deploy/manage_deploy.sh --action check-postgres
```

#### PostgreSQL performance and operations

The backend uses **synchronous SQLAlchemy** with `psycopg` (driver URL:
`postgresql+psycopg://…`). FastAPI runs sync endpoints in a thread pool; the chat
endpoint is sync so blocking DB/LLM work does not stall the event loop.

Tune the connection pool in `.env` (see `.env.example`):

| Variable | Dev (WSL) | Production |
|----------|-----------|------------|
| `DB_POOL_SIZE` | 5 | 10 |
| `DB_MAX_OVERFLOW` | 10 | 20 |
| `DB_POOL_TIMEOUT_SECONDS` | 30 | 30 |

Background workers (indexing, reprocess, Source Intelligence) throttle progress
writes (`PROGRESS_FLUSH_EVERY_ITEMS`, `PROGRESS_FLUSH_INTERVAL_SECONDS`) and
commit in batches. A cache-cleanup worker deletes expired rows using indexed
`expires_at` scans. Analytics are pre-aggregated hourly for fast dashboard reads.

#### Keeping chat responsive during indexing / Source Intelligence

Background jobs and live chat share one local Ollama, so a long-running job can
otherwise starve interactive requests. Two layers protect availability:

1. **App-level isolation (automatic).** Bulk indexing/reprocess embeddings run on
   a separate background pool, so chat query-embedding always keeps its own
   slots. Source Intelligence LLM calls reserve at most `N-1` of the `N` shared
   LLM slots (`Max concurrent LLM requests`), so a chat generation can always
   reach a slot without increasing total load on Ollama. The background
   embedding pool size is configurable in **Settings → Limits → Max concurrent
   background embedding requests** (keep it low, 1–2).

2. **Ollama-server tuning (recommended).** Set these on the Ollama service
   itself (e.g. `sudo systemctl edit ollama`), not in this app's `.env`:

   ```ini
   [Service]
   Environment="OLLAMA_NUM_PARALLEL=2"
   Environment="OLLAMA_MAX_LOADED_MODELS=2"
   Environment="OLLAMA_KEEP_ALIVE=30m"
   ```

   `OLLAMA_MAX_LOADED_MODELS=2` keeps the LLM and embedding models resident at
   the same time, avoiding slow model swaps when chat and indexing interleave.
   Apply with `sudo systemctl daemon-reload && sudo systemctl restart ollama`.

The dashboard health probes (Overview, performance) are cached for a few seconds
and use short timeouts, so transient Ollama slowness no longer flips the status
to a spurious "Ollama error".

Deploy script database actions:

```bash
bash deploy/manage_deploy.sh --action vacuum-analyze
bash deploy/manage_deploy.sh --action show-db-stats
bash deploy/manage_deploy.sh --action configure-postgres   # prints tuning guide
```

Recommended `postgresql.conf` for a small VPS (4 GB RAM): `shared_buffers=512MB`,
`effective_cache_size=2GB`, `work_mem=16MB`, `maintenance_work_mem=256MB`,
`max_connections=100`. Enable `pg_stat_statements` for slow-query analysis.
Set `DB_SLOW_QUERY_MS=500` to log queries exceeding 500 ms (secrets redacted).

### 4. Build the dashboard

```bash
bash deploy/install_dashboard.sh
# Produces dashboard/dist/ (static files for Nginx).
```

### 5. Configure Nginx

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/ai-site-agent
sudo nano /etc/nginx/sites-available/ai-site-agent   # set server_name + root path
sudo ln -s /etc/nginx/sites-available/ai-site-agent /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Nginx serves `dashboard/dist` on `/` and proxies `/api` to `127.0.0.1:8000`.

### 6. Run the backend via systemd

```bash
sudo cp deploy/systemd/ai-agent-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-agent-backend
sudo systemctl status ai-agent-backend
```

### 7. Open the dashboard

Visit `http://your-domain/` (or the server IP). The dashboard UI is in
**Ukrainian**. Then:

1. Go to **Індексація** (Indexing), enter the site URL and/or sitemap URL,
   choose a scan mode, and click **Почати індексацію** (Start indexing).
2. Watch progress (page/file counters) and the live log.
3. Open **Джерела** (Sources) to see indexed documents.
4. Open **Тест чату** (Chat Test) and ask a question about the site.
5. Ask something unrelated → you get the fallback answer.

---

## How to use indexing

The **Індексація** (Indexing) page controls what gets added to the knowledge
base. The dashboard labels are Ukrainian; the underlying settings keys are shown
below in English.

### Scan mode — `scan_mode`

Dashboard section: **Що сканувати**.

| Value             | Ukrainian label                       | Behaviour                                                                                 |
| ----------------- | ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `pages_only`      | Сканувати тільки сторінки сайту       | Index HTML pages only. Files are never downloaded or indexed. **(default)**              |
| `pages_and_files` | Сканувати сторінки і файли сайту      | Index HTML pages, and index discovered files **if file indexing is enabled**.            |
| `files_only`      | Сканувати тільки файли                | Index only files. Pages are crawled **only to discover file links** and are not stored.  |

### File indexing toggle — `enable_file_indexing`

Dashboard label: **Увімкнути індексацію файлів** (default `false`).

- When `false`, files are **never** downloaded or parsed, even in
  `pages_and_files` or `files_only` mode. Skipped files are logged as:
  `Індексація файлів вимкнена, файл пропущено: <URL>`.
- When `true`, files are indexed according to **`allowed_file_types`**
  (**Типи файлів для індексації**: `pdf`, `docx`, `txt`).

### Scan scope — `scan_all_pages` / `scan_all_files`

Dashboard section: **Обсяг сканування**.

- **Сканувати весь сайт** (`scan_all_pages`, default `false`): when enabled, the
  page limit is ignored and **all** discovered pages within the allowed domains
  are scanned.
- **Сканувати всі файли** (`scan_all_files`, default `false`): when enabled (and
  file indexing is on), the file limit is ignored and **all** discovered files of
  allowed types are indexed.

### Limits per indexing run

- **Максимум сторінок за один запуск** (`max_pages_per_run`):
  `0 = unlimited`. For large sites prefer an explicit limit, e.g. `1000`.
- **Максимум файлів за один запуск** (`max_files_per_run`):
  `0 = unlimited`. Only applies when file indexing is enabled.

> **“per indexing run”** means a single run started by clicking
> **Почати індексацію** (Start indexing). **`0` always means unlimited.**

### Indexing status counters

`GET /api/index/status` returns nested sections used by the Indexing page:

| Section | Meaning |
| ------- | ------- |
| `discovery` | URLs found during the **current** run (`discovered_urls`, `newly_discovered_urls`, …) |
| `queue` | Planner state for pages waiting / selected this run (`queued_pages_for_this_run`, `fresh_pages_skipped_until_refresh`, …) |
| `pages` | Processing outcomes this run (`processed_pages`, `indexed_new_pages`, `updated_pages`, …) |
| `files` | File discovery and processing counters |

`GET /api/index/queue-preview` uses the **same planner** as the worker and shows
what would be processed on the **next** run across all page sources in the DB.
During an active run, live `queue.queued_pages_for_this_run` updates after
discovery (and every 25 discovered pages). Fresh indexed pages are counted in
`skipped_fresh_pages` / `fresh_pages_skipped_until_refresh` and are not selected
until `next_refresh_at`.

Legacy flat fields (`discovered_pages`, `new_pages`, …) are still returned for
backward compatibility.

### Examples

**Example 1 — scan the whole website without files**

```json
{
  "scan_mode": "pages_only",
  "enable_file_indexing": false,
  "scan_all_pages": true,
  "max_pages_per_run": 0
}
```

Dashboard:
- **Що сканувати** → **Сканувати тільки сторінки сайту**
- **Сканувати весь сайт** → enabled

**Example 2 — scan pages and PDF/DOCX files**

```json
{
  "scan_mode": "pages_and_files",
  "enable_file_indexing": true,
  "allowed_file_types": ["pdf", "docx"],
  "scan_all_pages": true,
  "scan_all_files": true
}
```

Dashboard:
- **Що сканувати** → **Сканувати сторінки і файли сайту**
- **Увімкнути індексацію файлів** → enabled
- file types → **PDF**, **DOCX**
- **Сканувати весь сайт** → enabled
- **Сканувати всі файли** → enabled

**Example 3 — scan first 500 pages without files**

```json
{
  "scan_mode": "pages_only",
  "enable_file_indexing": false,
  "scan_all_pages": false,
  "max_pages_per_run": 500
}
```

Dashboard:
- **Що сканувати** → **Сканувати тільки сторінки сайту**
- **Максимум сторінок за один запуск** → `500`

### Source Intelligence

Dashboard block: **Source Intelligence** on the **Індексація** page (below the live progress card).

**What it does:** after pages are indexed, the agent builds a **semantic profile** per source (main topic, document type, keywords, supported intents). Retrieval uses these profiles to route queries to relevant pages instead of treating all chunks equally.

**When to run:**

| Situation | Action |
| --------- | ------ |
| First index finished | **Обробити потрібні** (Process needed) |
| New pages indexed | Same — only flagged sources are processed |
| Changed LLM/settings or full rebuild | **Переобробити всі** (Reprocess all) |
| Check workload without changes | **Оцінити без змін** (Estimate only) |

**Profile status counters:**

| UI label (UK) | Meaning |
| ------------- | ------- |
| Без профілю або застарілі | Sources missing a profile or whose content/settings changed |
| Профіль актуальний | Sources whose stored profile matches current content |
| LLM викликів при запуску | Approximate LLM calls if you click **Обробити потрібні** now |

**Progress block titles:**

| Title | Meaning |
| ----- | ------- |
| Source Intelligence | Real generation job (writes profiles to DB) |
| Source Intelligence — завершено | Generation finished |
| Оцінка Source Intelligence | Estimate running (read-only scan) |
| Оцінка завершена (дані не змінювались) | Estimate finished — **nothing was saved** |

**Performance settings** (collapsed section — admin tuning only):

| Setting | Meaning |
| ------- | ------- |
| Паралельні потоки | How many sources are processed at once **inside the backend thread pool** (not a separate server/worker machine) |
| Записів у БД за раз | Database commit batch size |
| Джерел за сторінку | Pagination size when reading sources from DB |

Settings (Agent Settings → **Source Intelligence** section):

- `enable_source_intelligence` — use profiles during retrieval
- `enable_llm_source_intelligence` — call LLM when building profiles (otherwise rules-only)
- `source_intelligence_worker_count` — **Parallel source processing**: Auto / 1 thread / 2 threads (UI select)
- `run_source_intelligence_inline_during_indexing` — run during index job (default off; use background job instead)

A collapsible **Settings guide** at the bottom of the Settings page explains every block in plain language.

API: `POST /api/index/source-intelligence`, `GET /api/index/source-intelligence-stats`, `GET /api/index/status` (when `run_mode=source_intelligence`).

---

## Redeploy on Linux without Docker

For day-to-day maintenance, use the **deployment manager** (recommended):

```bash
# Interactive menu (full / backend / frontend / clean reinstall / caches / reindex)
bash deploy/manage_deploy.sh

# Non-interactive examples
bash deploy/manage_deploy.sh --mode full
bash deploy/manage_deploy.sh --mode backend
bash deploy/manage_deploy.sh --mode frontend
bash deploy/manage_deploy.sh --mode clean --clear-db --clear-qdrant --clear-caches --yes
bash deploy/manage_deploy.sh --mode clear-caches
bash deploy/manage_deploy.sh --mode reindex
```

See [Deployment manager script](#deployment-manager-script) below for details.

After pulling new code, apply any new **Alembic migrations** with `alembic upgrade head` (or `python -m app.scripts.maintenance migrate`, also wired into `deploy/manage_deploy.sh --action run-migrations`). The backend verifies on startup that the database is migrated to the latest revision and **refuses to start otherwise** — there is no runtime auto-create. No Docker is involved.

> **Recommended after retrieval/indexing upgrades:** run **Reindex knowledge base** from the deploy manager (option 10) or `POST /api/index/reindex-all` so chunks populate the lexical index and new metadata.

### Manual redeploy (legacy)

Full redeploy (with backup):

```bash
cd /opt/ai-site-agent

sudo systemctl stop ai-agent-backend

# Back up the PostgreSQL database first.
bash deploy/manage_deploy.sh --action backup-postgres

git pull

cd backend
source .venv/bin/activate
pip install -r requirements.txt

# Apply Alembic migrations (schema is owned by migrations, no auto-create).
alembic upgrade head

cd ../dashboard
npm install
npm run build

sudo nginx -t
sudo systemctl start ai-agent-backend
sudo systemctl reload nginx

sudo systemctl status ai-agent-backend
curl http://127.0.0.1:8000/api/health
```

Short redeploy:

```bash
sudo systemctl stop ai-agent-backend
git pull
cd backend && source .venv/bin/activate && pip install -r requirements.txt
cd ../dashboard && npm install && npm run build
sudo systemctl start ai-agent-backend
sudo systemctl reload nginx
```

> The database connection follows `DATABASE_URL` in `.env`
> (PostgreSQL, e.g. `postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent`).
> Use `--action backup-postgres` / `--action restore-postgres` for backups.

---

## Deployment & operations manager

`deploy/manage_deploy.sh` is the **single operator entrypoint** for Linux servers
over SSH. It handles both **deployment** and **day-to-day operations** — no Docker:

- **Backend** — FastAPI in a Python venv, managed by **systemd** (`ai-agent-backend`)
- **Frontend** — Vite build served by **nginx** (static artifact, not a runtime service)
- **Ollama** — local LLM + embeddings (`ollama.service`)
- **Qdrant** — local vectors (`qdrant.service`)
- **PostgreSQL** — app database (the only supported engine; `postgresql.service`)

Configuration: `deploy/deploy.conf` + optional `deploy/deploy.local.conf`.

Module service names and `MANAGE_*` flags are centralized in `deploy/deploy.conf`.
Optional future units (`SCHEDULER_SERVICE_NAME`, `WORKER_SERVICE_NAME`) are picked up
automatically when set in `deploy.local.conf`.

### Typical SSH workflow (production)

```bash
ssh your-server
cd /opt/ai-site-agent

# First time: pin production paths
cp deploy/deploy.local.conf.example deploy/deploy.local.conf
# edit PROJECT_ROOT=/opt/ai-site-agent if needed

sudo bash deploy/manage_deploy.sh
```

The script shows a menu, asks clear **Y/n** questions with safe defaults, backs up
PostgreSQL (pg_dump) before destructive steps, and returns to the menu after each
action (failures do not drop you out of the session). Logs: `logs/deploy-*.log`.

**Most common update after `git pull` on the server:** choose **1) Full redeploy**.

**Dashboard-only UI change:** choose **3) Frontend only**, then hard-refresh the
browser (Ctrl+Shift+R).

**After indexing/retrieval code changes:** choose **10) Reindex knowledge**.

**Start the whole stack after reboot:** choose **11) Start all modules** or run
`bash deploy/manage_deploy.sh --action start-all`.

### Interactive menu

```bash
bash deploy/manage_deploy.sh
# or on production:
sudo bash deploy/manage_deploy.sh
```

| # | Action | When to use |
| - | ------ | ----------- |
| 1 | Full redeploy | Normal code update (backend + dashboard) |
| 2 | Backend only | Python/API/RAG changes |
| 3 | Frontend only | Dashboard UI changes |
| 4 | Clean reinstall | Wipe selected data + redeploy (confirms each step) |
| 5 | Restart services | Submenu: all modules or backend/nginx/ollama/qdrant |
| 6 | Show status | Module table + health probes + DB/index snapshot |
| 7 | DB migrations | Safe additive schema upgrade only |
| 8 | Rebuild frontend | `npm run build` without restarting backend |
| 9 | Clear caches | Faster fixes; keeps indexed sources |
| 10 | Reindex | Full site re-crawl after retrieval/index changes |
| 11 | Start all modules | Qdrant → Ollama → backend → nginx (+ health checks) |
| 12 | Stop all modules | Reverse order; stops nginx and backend |
| 13 | Restart all modules | Full stack restart + health checks |
| 14–16 | Start/stop/restart one module | Pick backend, nginx, ollama, or qdrant |
| 17 | Show logs | `journalctl` for selected module (last 100 lines) |
| 0 | Exit | |

### Operations (CLI)

```bash
bash deploy/manage_deploy.sh --action status
bash deploy/manage_deploy.sh --action start-all
bash deploy/manage_deploy.sh --action stop-all
bash deploy/manage_deploy.sh --action restart-all
bash deploy/manage_deploy.sh --action start --module backend
bash deploy/manage_deploy.sh --action stop --module ollama
bash deploy/manage_deploy.sh --action restart --module qdrant
bash deploy/manage_deploy.sh --action logs --module backend
```

Start order: **Qdrant → Ollama → backend → (worker/scheduler if configured) → nginx**.  
Stop order: **nginx → backend → worker/scheduler → Ollama → Qdrant**.

If a systemd unit is missing or management is disabled (`MANAGE_OLLAMA=false`, etc.),
the script logs a warning and continues with the remaining modules.

### Deploy (non-interactive CLI)

```bash
bash deploy/manage_deploy.sh --mode full
bash deploy/manage_deploy.sh --mode backend
bash deploy/manage_deploy.sh --mode frontend
bash deploy/manage_deploy.sh --mode clean --clear-db --clear-qdrant --clear-caches --yes
bash deploy/manage_deploy.sh --mode clear-caches
bash deploy/manage_deploy.sh --mode reindex
bash deploy/manage_deploy.sh --mode restart    # alias for --action restart-all
bash deploy/manage_deploy.sh --mode status
bash deploy/manage_deploy.sh --mode migrate
```

Useful flags: `--no-git-pull`, `--backup-db`, `--recreate-venv`, `--use-staging`
(sync from `/tmp/ai-site-agent-deploy` after `deploy/prepare_staging.sh`),
`--sync-from-dev` / `--no-sync-from-dev` (when deploying from a dev checkout to
`/opt/ai-site-agent` on the same machine).

**Dev checkout → `/opt` on one server:** If you run the script from
`~/projects/ai-site-agent` but production lives at `/opt/ai-site-agent`, choose
**Yes** when asked to sync code (or pass `--sync-from-dev`). A plain `git pull` in
`/opt` does not pick up uncommitted work in your dev tree — rsync copies the current
checkout instead (DB, venv, and `node_modules` are preserved).

### What clean mode can remove

Only items you confirm (interactive) or pass via CLI flags:

- **PostgreSQL database** (`--clear-db`) — drops and recreates the database, then re-runs Alembic migrations
- **Qdrant collections** (`--clear-qdrant`) — main knowledge + answer-cache collections
- **Caches only** (`--clear-caches`) — `retrieval_cache` + `answer_cache` tables (and answer-cache Qdrant collection)
- **Frontend dist/** (`--clear-frontend`)
- **Python venv** (`--recreate-venv`) — off by default

Backups are stored under `backups/<db>.YYYYMMDD_HHMMSS.dump` (pg_dump custom
format) when enabled. Deploy logs: `logs/deploy-*.log`.

### Maintenance CLI (called by the deploy manager)

From `backend/` with venv active:

```bash
python -m app.scripts.maintenance clear-caches
python -m app.scripts.maintenance clear-qdrant --main --answer-cache
python -m app.scripts.maintenance migrate            # alembic upgrade head
python -m app.scripts.maintenance reset-db           # DROP + rebuild schema (destructive)
python -m app.scripts.maintenance trigger-reindex
python -m app.scripts.maintenance status
```

`reset-db` drops all tables in the configured PostgreSQL database and rebuilds the
schema via Alembic — it is destructive. For point-in-time backups use
`--action backup-postgres` / `--action restore-postgres`.

### Migrating existing SQLite data to PostgreSQL

If you are upgrading from an older SQLite-based install, copy your data once with
the migration utility (SQLite is not supported at runtime — this is a one-time
import into a freshly-migrated PostgreSQL database):

```bash
cd backend && alembic upgrade head           # create the PostgreSQL schema
python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path ./ai_site_agent.db \
    --postgres-url postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent
# Options: --dry-run, --truncate-target, --skip-caches/--include-caches, --skip-logs
# or via the deploy manager:
bash deploy/manage_deploy.sh --action migrate-sqlite-to-postgres --module ./backend/ai_site_agent.db
```

### Production path example

```bash
cp deploy/deploy.local.conf.example deploy/deploy.local.conf
# PROJECT_ROOT=/opt/ai-site-agent
sudo bash deploy/manage_deploy.sh
```

If the server has no git checkout (files copied via rsync), set `GIT_PULL_DEFAULT=no`
in `deploy.local.conf` and use `--use-staging` after `deploy/prepare_staging.sh`
on your dev machine.

**`.env` line endings:** If you see `$'\r': command not found`, the `.env` file has
Windows (CRLF) line endings. The deploy manager strips them automatically; you can
also fix permanently with: `sed -i 's/\r$//' .env`

**`npm not found` under sudo:** Node installed via **nvm** is on your user PATH, not
root's. The deploy script auto-detects nvm for `$SUDO_USER`; if the warning persists,
set `NPM_BIN` in `deploy/deploy.local.conf` or install Node system-wide
(`sudo apt install nodejs npm` or Nodesource).

---

## Example Ollama commands

```bash
ollama pull qwen2.5:7b
ollama pull bge-m3
ollama list
```

## Example backend run (without systemd)

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Example chat API request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Яка комісія за відкриття рахунку?","session_id":"test"}'
```

Response shape (public widget — `debug: false`):

```json
{
  "request_id": "uuid",
  "answer": "string",
  "sources": [
    {"title": "string", "url": "string", "source_type": "page", "score": 0.0}
  ],
  "used_context": true,
  "cache_hit": false,
  "cache_type": "none",
  "timing": {
    "total_ms": 0,
    "retrieval_ms": 0,
    "generation_ms": 0,
    "polish_ms": 0
  }
}
```

Dashboard **Тест чату** sends `"debug": true` and additionally receives
`trace` (pipeline steps + retrieved chunks) and `metadata` (request id, session,
IP, user agent, referrer, knowledge version, retrieval mode).

`cache_type` is one of `none`, `retrieval` (chunks reused from the retrieval
cache) or `answer` (the full answer was served from the semantic answer cache).

---

## Performance, answer quality, and caching

The chat pipeline is optimized for low latency and clean, grounded Ukrainian
answers. New flow for `POST /api/chat`:

```text
normalize query
  → semantic answer cache  (hit → return cached answer + sources)
  → retrieval cache        (hit → reuse cached chunks)
  → retrieve from Qdrant → rerank → threshold/trim
  → no relevant context?   → fallback answer (LLM is NOT called)
  → grounded LLM answer
  → optional Ukrainian polish pass
  → format source links
  → store retrieval + answer caches
  → return answer + cache metadata + timings
```

### Retrieval cache

Caches retrieved/reranked chunks keyed by the normalized query plus
`knowledge_version`, `top_k`, `similarity_threshold`, the Qdrant collection and
the rerank flag. Repeated/similar questions skip the Qdrant + rerank work while
the knowledge base is unchanged. Controlled by **Увімкнути кеш пошуку** and
**TTL кешу пошуку (сек.)** (default `3600`).

### Semantic answer cache

Stores query embeddings in a dedicated Qdrant collection
(`<collection>_answer_cache`) and answer metadata in the `answer_cache`
PostgreSQL table. A new question that is semantically close to a previously answered one
(cosine similarity ≥ **Поріг схожості кешу відповідей**, default `0.93`), shares
the current `knowledge_version` and is not expired, is answered instantly
without calling the LLM. Controlled by **Увімкнути кеш відповідей**, **TTL кешу
відповідей (сек.)** (default `86400`) and **Максимум кешованих відповідей**
(default `5000`, oldest entries are purged).

### Cache invalidation (knowledge versioning)

A `knowledge_version` integer (stored on the settings row) is bumped whenever
indexed content changes: a full index/reindex completes with new content,
**Переіндексувати все** runs, a source is reindexed with changed content, or a
source is deleted. Cache entries carry the version they were created with, so
stale entries are ignored and recomputed automatically. `reindex-all` also
clears both caches outright.

### Source links

When the answer is grounded (`used_context = true`) and **Показувати посилання
на джерела** is on, the response includes up to 5 deduplicated sources (by URL),
sorted by relevance. The dashboard **Тест чату** page renders them as clickable
links under **Джерела відповіді** and shows whether the answer came from cache.

### Ukrainian polish pass

When **Стилістичне доопрацювання української відповіді** is on and the response
language is Ukrainian, a second local LLM pass rewrites the answer into clean,
grammatical Ukrainian without changing facts, numbers, links or meaning. In
**Швидкий режим** very short answers skip this pass.

### Fast mode

**Швидкий режим** reduces `top_k`, uses a shorter prompt, and skips polishing of
short answers — without weakening the grounding/threshold logic. If no relevant
context is found, the fallback answer is always returned immediately without
calling the LLM.

### Timing instrumentation

Chat logs record `cache_hit`, `cache_type`, `retrieval_ms`, `generation_ms` and
`polish_ms` to help diagnose latency. These are visible on the **Журнали** page.
Full **answer traces** (see below) are stored in the `answer_traces` table and
exposed via `/api/traces` for deeper debugging.

---

## Production performance and scalability

The backend is designed for concurrent dashboard and widget traffic on a single
Linux host. Key mechanisms:

### Concurrency limits

Configurable semaphores protect local Ollama from overload:

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `max_concurrent_chat_requests` | 20 | Total in-flight chat requests |
| `max_concurrent_llm_requests` | 2 | Parallel LLM generation calls |
| `max_concurrent_embedding_requests` | 2 | Parallel embedding calls |

When limits are exceeded the API returns **HTTP 429** with a Ukrainian message:
*«Система тимчасово перевантажена. Спробуйте ще раз за кілька секунд.»*

Tune these on **Налаштування агента → Обмеження навантаження та таймаути**.
Size Ollama according to your GPU/CPU and model — a 7B model on CPU may need
`max_concurrent_llm_requests = 1`.

### Timeouts

Separate timeouts for chat total duration, Ollama generation, Ollama embeddings
and Qdrant prevent hung requests from blocking workers.

### Async + connection reuse

Chat endpoints are async. Ollama uses a shared HTTP client; Qdrant and database
sessions are reused per request lifecycle.

### PostgreSQL tuning

A pooled connection (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`,
`DB_POOL_PRE_PING`) plus indexes on `chat_logs`, `sources`, `chunks`,
`retrieval_cache`, `answer_cache`, `index_jobs` and `answer_traces` keep reads
fast. Lexical search uses a PostgreSQL `tsvector` GIN index on `chunks`. Unlike a
single-writer SQLite file, PostgreSQL handles concurrent indexing + chat without
write-lock contention.

### Running with multiple workers

For production, run the backend behind Nginx with Gunicorn + Uvicorn workers:

```bash
cd /opt/ai-site-agent/backend
source .venv/bin/activate
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 127.0.0.1:8000
```

Recommended worker count: `(2 × CPU cores) + 1`, capped by available RAM and
Ollama capacity. Qdrant should run as a **separate systemd service**. Ollama
must be sized for your model/GPU. PostgreSQL comfortably supports multiple
backend workers/instances behind Nginx sharing the same database.

Example systemd unit: `deploy/systemd/ai-agent-backend.service`. Nginx config:
`deploy/nginx/ai-site-agent.conf`.

### Caching under load

Retrieval and semantic answer caches are checked **before** expensive LLM calls.
Monitor cache hit rate on **Аналітика** or `GET /api/system/performance`.

### Metrics to monitor

- Active/queued chat requests (`/api/system/performance`)
- Average and P95 latency (`/api/analytics/summary`)
- Cache hit rate
- Fallback rate (answers without context)
- Ollama and Qdrant health (`/api/health`)

---

## Answer tracing and diagnostics

Every chat request receives a unique `request_id`. When tracing is enabled the
pipeline records steps such as normalization, cache lookups, dense/lexical
retrieval, hybrid merge, reranking, threshold filter, context building, LLM
generation, Ukrainian polish and source formatting.

### Dashboard Chat Test

**Тест чату** is a split-screen diagnostic tool:

- **Left:** conversation, sources, cache status, timing
- **Right:** **Шлях пошуку відповіді** — timeline of pipeline steps with
  duration and details
- **Знайдені фрагменти** — retrieved chunks with dense/lexical/final scores
  and whether each chunk was used in context
- **Інформація про запит** — request id, session id, IP, user agent, referrer

Use this to debug cases like *«курси валют є на головній, але агент їх не
знаходить»*: check whether homepage chunks appear in retrieval, their scores,
and whether they pass the similarity threshold.

### Trace API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/traces` | List traces (filters: session_id, date range, cache_hit, query) |
| GET | `/api/traces/{request_id}` | Full trace for one request |

Traces are stored when **enable_trace_storage** is on (default). Metadata
logging (IP, user agent, referrer) is controlled by
**enable_request_metadata_logging**. Cookies, auth headers and tokens are never
stored.

### Public widget vs debug mode

Production website widgets should call `/api/chat` with `"debug": false` (default)
so internal retrieval details are not exposed. The dashboard test page uses
`"debug": true`.

---

## Dashboard design

The admin dashboard uses a clean, modern SaaS layout inspired by premium
enterprise products: light neutral background, soft card shadows, left sidebar
navigation, and metric cards. The UI supports **Ukrainian (default) and English**
via a language switcher in the top header. Preference is stored in
`localStorage` and can also be saved as `dashboard_language` in agent settings.
This is separate from `default_response_language`, which controls the language
of AI answers for end users.

Pages:

- **Overview / Огляд** — system health
- **Indexing / Індексація** — crawl and reindex
- **Sources / Джерела** — indexed content
- **Chat Test / Тест чату** — answer debugger with trace panel
- **Analytics / Аналітика** — usage and performance metrics
- **Logs / Журнали** — chat history
- **Agent Settings / Налаштування агента** — models, retrieval, caching, tracing, concurrency

---

## Retrieval quality tuning

The agent uses **hybrid retrieval** so it can reliably find content that exists
on the site — including short, structured homepage blocks such as currency
rates, tariffs, contacts and working hours.

### Dense vs lexical vs hybrid (`retrieval_mode` → **Режим пошуку**)

- **Векторний** (`dense`) — semantic vector search via embeddings + Qdrant.
  Great for meaning, weaker for short keyword queries.
- **Ключові слова** (`lexical`) — keyword search over chunk text, page title and
  section heading via PostgreSQL full-text search (`tsvector`/`ts_rank` with a GIN
  index, `simple` config). Great for exact terms.
- **Гібридний** (`hybrid`, default) — runs both, merges and reranks with score
  fusion. Recommended.

### Why short business queries need hybrid

A query like **«курси валют»** is only 2 words. Pure vector search may score the
homepage rates block below the similarity threshold and return the fallback. The
lexical layer matches the exact words in the section heading/table, and the
reranker boosts it. So hybrid retrieval finds it even when dense search alone
would miss it.

### Ranking boosts

The reranker combines dense score, lexical score and several boosts (all
configurable on **Налаштування агента**):

- **Підсилення збігу в назві сторінки** (`title_match_boost`, `0.15`)
- **Підсилення збігу в заголовку секції** (`heading_match_boost`, `0.15`)
- **Підсилювати головну сторінку** / **Підсилення для головної сторінки**
  (`homepage_boost_enabled`, `homepage_boost_value` = `0.10`)
- **Підсилення ключових слів для коротких запитів**
  (`short_query_lexical_boost`, `0.20`) — applied to 1–4 word queries.

### Query expansion (`enable_query_expansion` → **Розширення пошукового запиту**)

A small synonym/alias dictionary widens recall for common business terms, e.g.
«курси валют» also matches «курс валют», «обмін валют», «exchange», «USD/EUR».

### Structured indexing

During indexing, HTML pages are split into **heading-aware blocks**, tables are
**flattened into readable rows** (`USD | купівля 41.00 | продаж 41.50`), and
short high-value blocks are preserved as their own chunks. Each chunk stores its
page title, section heading, `is_homepage`, `is_structured_block` and a
`content_type_hint` (`rates`, `contacts`, `tariffs`, `schedule`, `faq`,
`general`). The page title and heading are prepended to each chunk so both dense
and lexical search "see" the section context.

### Debugging (`enable_retrieval_debug` → **Режим діагностики пошуку**)

When enabled, the chat response includes a `retrieval_debug` block and the
**Тест чату** page shows a "Діагностика пошуку" panel: normalized query, query
variants, the FTS match expression, and per-chunk dense/lexical/final scores.

### Example

- Query: **«курси валют»**
- Expected: if the homepage (or a dedicated rates page) contains a visible
  "Курси валют" block with USD/EUR values, at least one chunk includes both the
  heading and the rate values, hybrid retrieval surfaces that chunk, and the
  answer cites the homepage / rates page as a source.

### Agent Knowledge Profile

Retrieval is **configurable per website**, not hardcoded for a specific industry.
Configure in the dashboard:

**Admin → Профіль знань / Knowledge Profile** (`/knowledge-profile`)

| Area | Purpose |
| ---- | ------- |
| Site identity | Organization name, aliases, entity type, site subject |
| Overview query patterns | Phrases that trigger entity overview (e.g. «розкажи про», «about us») |
| Important topics | Topic keys, aliases, preferred doc types, answer strategy |
| Document type rules | URL/title/heading patterns → `about_page`, `news_page`, … |
| Content hint rules | Text patterns → `rates`, `contacts`, `faq`, … |
| Source priority rules | Per-intent boost/deprioritize document types and hints |
| Query expansion rules | Trigger patterns + terms with `{{organization_name}}` placeholders |

**Presets:** generic corporate, bank/financial, ecommerce, SaaS, documentation portal, government, university.

**Import / export:** JSON profile for reuse on another site.

**After changing document type or content hint rules:** run **Переіндексувати все** so chunks get updated metadata.

**Chat Test debug** shows **Applied configuration** (intent, matched topic, boosts, expansions).

API: `GET/PUT /api/knowledge-profile`, `/presets`, `/export`, `/import`.

Broad queries like **«укрсиббанк»**, **«кредити»** or **«курси валют»** are routed by
**query intent** to appropriate document types via the profile — not random news chunks.
Settings `enable_intent_aware_retrieval`, `enable_document_type_boosting`,
`enable_canonical_source_selection`, `enable_news_deprioritization_for_overview_queries`,
and `fallback_second_pass_enabled` default **on**.

**Example — «укрсиббанк»:** the answer should summarize from «Про банк» /
«Історія банку» / homepage profile content, not a mix of unrelated news.
**A full reindex is required** after upgrading so existing chunks receive
`document_type` metadata in PostgreSQL and Qdrant.

### Reindex after changing indexing/retrieval behavior

Because chunking/indexing metadata changed, **a full reindex is recommended**
after upgrading. Use **«Переіндексувати все»** on the **Індексація** page (or
`POST /api/index/reindex-all`). This rebuilds chunks, the lexical FTS index and
the Qdrant vectors, and bumps the knowledge version so caches reset.

> Дашборд-нагадування: «Після зміни логіки індексації або пошуку рекомендується
> виконати повну переіндексацію сайту.»

---

## Local development

Run the backend (auto-reload) and the Vite dev server in two terminals:

```bash
bash scripts/run_backend.sh        # http://127.0.0.1:8000
bash scripts/run_dashboard_dev.sh  # http://localhost:5173  (proxies /api)
```

The dev server proxies `/api` to the backend, so no CORS config is needed.

If files are owned by `www-data`, Cursor cannot edit them. Fix once:

```bash
sudo bash scripts/fix-dev-permissions.sh
# or:
sudo chown -R $USER:$USER ~/projects/ai-site-agent
```

Work only in `~/projects/ai-site-agent`. Deploy to `/opt` with:

```bash
sudo bash deploy/manage_deploy.sh --mode full --sync-from-dev --yes
```

---

## Dashboard authentication

The admin dashboard uses JWT bearer authentication.

### Default login (first install only)

When no users exist in the database, a default admin is created automatically:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `фвьшт` |

**Change this password immediately after first login** (Users → admin → Change password).

If users already exist, the default admin is **not** recreated and passwords are **not** reset on startup.

### Environment variables

Add to `.env` (see `.env.example`):

```env
JWT_SECRET_KEY=your-long-random-secret
JWT_EXPIRE_MINUTES=480
```

- In production (`APP_ENV=production`), set `JWT_SECRET_KEY` to a strong random value.
- If missing in development, a temporary insecure default is used and a warning is logged.

### Roles

| Role | Access |
|------|--------|
| **admin** | Full dashboard + user management + settings + knowledge profile |
| **operator** | Overview, indexing, sources, chat test, analytics, logs |
| **viewer** | Overview, analytics, logs (read-only areas) |

### Public vs protected APIs

- **Public:** `/api/health`, `/api/chat`, `/api/chat/stream` (website widget)
- **Protected:** settings, indexing, sources, analytics, logs, chat sessions, knowledge profile, user management

---

## API endpoints

| Method | Path                              | Description                          |
| ------ | --------------------------------- | ------------------------------------ |
| GET    | `/api/health`                     | App / Ollama / Qdrant status         |
| GET    | `/api/settings`                   | Read agent settings                  |
| PUT    | `/api/settings`                   | Update agent settings                |
| GET    | `/api/sources`                    | List indexed sources (paginated)     |
| GET    | `/api/sources/{id}`               | Get one source                       |
| DELETE | `/api/sources/{id}`               | Delete source (PostgreSQL + Qdrant)  |
| POST   | `/api/sources/{id}/reindex`       | Reindex a single source              |
| POST   | `/api/index/start`                | Start an indexing job                 |
| POST   | `/api/index/stop`                 | Request a running job to stop        |
| POST   | `/api/index/reindex-all`          | Clear all sources + Qdrant, reindex  |
| GET    | `/api/index/status`               | Current/last job status + counters   |
| POST   | `/api/chat`                       | Grounded RAG chat (returns request_id, timing) |
| POST   | `/api/chat/stream`                | Streaming chat (stub / optional)               |
| GET    | `/api/chat/logs`                  | Chat logs (paginated)                          |
| GET    | `/api/traces`                     | Answer traces (paginated, filterable)          |
| GET    | `/api/traces/{request_id}`        | Single answer trace                            |
| GET    | `/api/analytics/summary`          | Usage summary metrics                          |
| GET    | `/api/analytics/timeseries`       | Hourly requests/latency/cache                  |
| GET    | `/api/analytics/top-unanswered`   | Top fallback queries                           |
| GET    | `/api/analytics/slow-queries`     | Slowest requests                               |
| GET    | `/api/system/performance`         | Active requests, queue, latency, service status  |
| GET    | `/api/models`                     | Installed Ollama models                        |
| GET    | `/api/ollama/status`              | Ollama reachability + models                   |
| GET    | `/api/knowledge-profile`          | Read agent knowledge profile                   |
| PUT    | `/api/knowledge-profile`          | Update knowledge profile                       |
| GET    | `/api/knowledge-profile/presets`  | List profile presets                           |
| POST   | `/api/knowledge-profile/presets/load` | Load a preset into profile                 |
| GET    | `/api/knowledge-profile/export`   | Export profile as JSON                         |
| POST   | `/api/knowledge-profile/import`   | Import profile from JSON                       |
| POST   | `/api/auth/login`                 | Dashboard login (JWT)                          |
| GET    | `/api/users`                      | List dashboard users (admin)                   |

Interactive docs are available at `http://127.0.0.1:8000/docs`.

---

## Configuration

Process-level settings come from `.env` (see `.env.example`). Agent behaviour
settings (models, thresholds, prompts, chunking, fallback answer, etc.) are
stored in PostgreSQL and editable from the **Agent Settings** page.

Default models:

- LLM: `qwen2.5:7b`
- Embeddings: `bge-m3`

Default chunking: size `800`, overlap `120`. Default `top_k` `5`,
`similarity_threshold` `0.55`.

---

## Tests

```bash
bash scripts/run_tests.sh
# or
cd backend && .venv/bin/pytest
```

Tests cover chunking behaviour, content-hash stability, and the retrieval
threshold / no-hallucination fallback logic.

---

## Notes & limitations (MVP)

- Single indexing job at a time, run in a background thread (no Celery/Redis).
- PostgreSQL is the only supported app database (connection pooling + indexes);
  schema is managed by Alembic migrations.
- WordPress sites work via sitemap + crawling; optional `/wp-json` discovery is
  attempted automatically when a site URL is provided.
- The similarity threshold default (`0.55`, cosine) may need tuning per embedding
  model and content; adjust it on the Settings page.
