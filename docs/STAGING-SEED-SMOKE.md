# Staging seed & smoke plan

**Purpose:** Reproducible staging validation before Release 0.4+ schema work (Step 027+).  
**Stack:** **Primary — classic Linux deployment:** `/opt/ai-site-agent`, systemd, nginx, host Postgres/Qdrant/Ollama via `deploy/manage_deploy.sh`. Docker may exist for optional CI validation but is **not** required for staging smoke.

---

## Prerequisites

| Step | Command |
|------|---------|
| Release gate (local/CI) | `make release-check` |
| Deploy to server | `make deploy` |
| Smoke HTTP checks | `make smoke` |
| Full path | `make deploy-smoke` |

See also: [DEPLOYMENT.md](DEPLOYMENT.md), [RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md).

---

## 1. Admin user

### Default (fresh database)

On first startup with **no users in DB**, the backend seeds:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `фвьшт` |
| Role | `admin` |

**Change the password immediately** after first login: Dashboard → Users → admin → Change password.

### Verify login

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"фвьшт"}' | python3 -m json.tool
```

Expect `access_token` in response.

### Existing database

If users already exist, the default admin is **not** recreated. Use your stored admin credentials or reset via DB (ops-only).

---

## 2. Load a generic fixture site

Use a **small public site** you control or a stable demo site. Example: your own marketing site or documentation site with a few pages.

### Configure site URL

1. Log in to dashboard → **Settings**
2. Set **Site URL** (e.g. `https://example.com`)
3. Save

Or via API (with admin token):

```bash
TOKEN="<access_token>"
curl -s -X PUT http://127.0.0.1:8000/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"site_url":"https://example.com"}'
```

### Recommended indexing settings (staging)

| Setting | Staging value | Why |
|---------|---------------|-----|
| Scan mode | `pages_only` | Faster, fewer moving parts |
| `enable_file_indexing` | `false` | Avoid large downloads on first smoke |
| Page limit | `20–50` | Enough for chat smoke, not a full crawl |

---

## 3. Run indexing

### Dashboard

1. **Indexing** → confirm site URL
2. Click **Start indexing** (Почати індексацію)
3. Wait until job status is **completed**

### API

```bash
curl -s -X POST http://127.0.0.1:8000/api/index/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

curl -s http://127.0.0.1:8000/api/index/status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Reindex (after code deploy)

```bash
sudo bash deploy/manage_deploy.sh --mode reindex
# or
curl -s -X POST http://127.0.0.1:8000/api/index/reindex-all \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4. Smoke verification checklist

Run automated smoke:

```bash
make smoke
# with chat (needs Ollama + indexed content):
SMOKE_CHAT=1 make smoke
```

### Manual verification

| Check | Command | Expected |
|-------|---------|----------|
| Health | `curl -s http://127.0.0.1:8000/api/health` | `app.status=ok`, DB reachable |
| Build metadata | `curl -s http://127.0.0.1:8000/api/build` | `release`, `git_commit`, `alembic_head`, versions |
| Metrics | `curl -s http://127.0.0.1:8000/api/metrics \| grep kos_memory_version` | gauge present |
| Operational JSON | `curl -s http://127.0.0.1:8000/api/metrics/operational` | `memory_version`, `knowledge_version` |
| Settings | `curl -s http://127.0.0.1:8000/api/settings -H "Authorization: Bearer $TOKEN"` | flags present, default OFF |

---

## 5. Chat smoke — Executive flag OFF (default)

Default ship path. No env change required.

```bash
SMOKE_CHAT=1 make smoke
```

Or manual:

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is on the homepage?","debug":false,"bypass_cache":true}' \
  | python3 -m json.tool
```

Expect non-empty `answer` when indexing completed and Ollama models are pulled (`qwen2.5:3b`, `bge-m3`).

---

## 6. Chat smoke — Executive flag ON

**Staging experiment only.** Document results before any production enable.

### Enable

Edit `/opt/ai-site-agent/.env`:

```bash
KNOWLEDGE_OS_EXECUTIVE_ENABLED=true
```

Restart backend:

```bash
sudo systemctl restart ai-agent-backend
curl -s http://127.0.0.1:8000/api/build | python3 -m json.tool
# feature_flags.KNOWLEDGE_OS_EXECUTIVE_ENABLED should be true
```

### Test chat

```bash
SMOKE_CHAT=1 make smoke
```

Compare answer path / traces with flag OFF. Record in ops log.

### Rollback (required after test)

```bash
# In /opt/ai-site-agent/.env:
KNOWLEDGE_OS_EXECUTIVE_ENABLED=false

sudo systemctl restart ai-agent-backend
make smoke
```

See [0.3-rollback.md](releases/0.3-rollback.md).

---

## 7. Release readiness tiers

See [LIFECYCLE.md](../LIFECYCLE.md) for the full model.

| Tier | Meaning | Gate |
|------|---------|------|
| **Engineering-ready** | `make release-check` | Next RFC step (e.g. 027) may begin |
| **Staging-validated** | Deploy + smoke on real server | Production-ready review |
| **Production-ready** | Staging + rollback + sign-off | Production deployment |

**Production deployment is blocked until staging-validated.** Engineering (Step 027+) is **not** blocked by pending staging ops.

---

## 8. Rollback verification

Before production ship, confirm rollback path (no downgrade required for flag-only rollback):

1. Set `KNOWLEDGE_OS_EXECUTIVE_ENABLED=false` and migration flags OFF in Settings
2. `sudo systemctl restart ai-agent-backend`
3. `make smoke` green
4. Read [0.3-rollback.md](releases/0.3-rollback.md)

```bash
make rollback-staging   # prints checklist
```

---

## 9. Troubleshooting

| Symptom | Action |
|---------|--------|
| Login fails | Confirm admin user exists; check default password only on fresh DB |
| Chat empty answer | Index not complete; Ollama down; models not pulled |
| `/api/build` git_commit null | Normal if deploy tree has no `.git`; redeploy via `make deploy` writes `.build-info.json` |
| Metrics missing | Migrations not at head — `cd backend && .venv/bin/alembic upgrade head` |

Logs: `sudo journalctl -u ai-agent-backend -n 100 --no-pager`
