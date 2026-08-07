# G9-P2 Cold-Demo Execution Evidence — Release 1.0 tip `71b308f`

**Date:** 2026-08-07  
**Reviewer:** Principal AI Architect / Release Manager (automated + live walkthrough)  
**Protocol:** `docs/releases/S008-cold-demo-protocol.md`  
**Runtime tip:** `71b308fdb9d0ebbf35fd4e3611e6fadb65d3687e`  
**Deploy:** `/opt/ai-site-agent/deployments/20260807_060415-71b308f.json` (SUCCESS; verify-release PASS; smoke PASS)  
**Role executed:** `admin` (full Mode-off walkthrough)  
**Base URL:** `http://127.0.0.1`

## Preconditions

| Check | Result |
|-------|--------|
| Deployed tip matches origin/main | PASS (`71b308f`) |
| `/api/build` release `1.0`, `closed_1_0=true` | PASS |
| `enable_knowledge_understanding=false` | PASS (smoke + settings) |
| Dashboard reachable; Engineering Mode default off | PASS |

## Mode-off checklist results

### 4.1 Landing / Home

| Item | Result |
|------|--------|
| Login lands on `/home` | PASS |
| Home shows readiness + next action | PASS (“Is the agent ready? Here's what to do next.” + View progress CTA) |
| No “Overview” label on Home chrome | PASS |

### 4.2 No Overview home

| Item | Result |
|------|--------|
| No Overview nav entry | PASS |
| `/overview` → `/home` | PASS |
| Product nav does not present Overview | PASS |

### 4.3 Knowledge

| Item | Result |
|------|--------|
| Library / Update / Site under Knowledge | PASS |
| Library / Update / Site routes load | PASS |

### 4.4 Ask

| Item | Result |
|------|--------|
| Ask in top-level nav | PASS |
| `/chat` → `/ask` | PASS |
| Ask shows answer + sources region; no Eng diagnostics by default | PASS |

### 4.5 Insights

| Item | Result |
|------|--------|
| Performance + Activity under Insights | PASS |
| Screens load | PASS |

### 4.6 Settings

| Item | Result |
|------|--------|
| General / Models / Answers / Access | PASS |
| Answers: Automatic / Fast / Balanced / High precision only (no retrieval weight knobs) | PASS |

### 4.7 Engineering Mode off

| Item | Result |
|------|--------|
| No Engineering nav group | PASS |
| Mode toggle on Settings → General, unchecked | PASS |
| `/engineering/status` does not render Eng content (redirects to General) | PASS |

## Verdict

**G9-P2 execution: PASS** for admin Mode-off cold demo on tip `71b308f`.

Operator / viewer role cold demos were not separately recorded in this pass; admin covers the full Mode-off product surface. Remaining role matrix may be treated as accepted operational follow-up (not must-resolve) because IA/guards are role-tested in the RFC-101 unit suite and smoke login path already exercised authenticated settings.
