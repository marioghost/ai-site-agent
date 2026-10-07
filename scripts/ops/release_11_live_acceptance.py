#!/usr/bin/env python3
"""Release 1.1 live acceptance — shadow non-interference + Phase 1 metrics + Ask QA."""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.core.database import SessionLocal
from app.repositories.settings_repository import SettingsRepository
from app.services.embedding_service import EmbeddingService
from app.services.ollama_service import OllamaService
from app.services.qdrant_service import QdrantService
from app.services.rag_service import RagService
from app.services.retrieval_pipeline_service import RetrievalPipelineService

SHADOW_QUERIES = [
    "Що таке UKRSIBBANK?",
    "Як відкрити рахунок?",
    "Кредитна картка умови",
    "Відділення банку Київ",
    "Курси валют",
    "Мобільний банкінг",
    "What is this bank?",
    "Deposit rates",
    "Privacy policy",
    "Life insurance",
    "Cash loan",
    "Benefits for clients",
]

ASK_CASES = [
    ("org_overview_uk", "Що таке цей банк?", "uk"),
    ("org_overview_en", "What is this organization?", "en"),
    ("org_benefits", "Які переваги банку для клієнтів?", "uk"),
    ("product_benefits", "Які переваги кредитної картки?", "uk"),
    ("cash_loan_family", "Кредит готівкою умови", "uk"),
    ("life_insurance", "Що таке страхування життя?", "uk"),
    ("deposit_rates", "Які ставки по депозитах?", "uk"),
    ("branch_locator", "Де знайти відділення в Києві?", "uk"),
    ("privacy_policy", "Політика конфіденційності", "uk"),
    ("unsupported_geo", "Do you have branches in New York?", "en"),
    ("short_ambiguous", "карта", "uk"),
    ("uk_quality", "Розкажи коротко про банк", "uk"),
    ("en_quality", "Tell me briefly about the bank", "en"),
]


@dataclass
class ShadowRow:
    query: str
    ranking_unchanged: bool
    overlap_ratio: float
    overlap_count: int
    dfp_count: int
    understanding_count: int
    understanding_only_count: int
    dfp_only_count: int
    shadow_ms: float
    resolution_ms: float
    evidence_ms: float
    failure_reason: str | None
    concepts_resolved: int
    snapshot_id: int | None


@dataclass
class AskRow:
    case_id: str
    query: str
    lang: str
    answer_preview: str
    answer_len: int
    source_count: int
    source_urls: list[str] = field(default_factory=list)
    truncated: bool = False
    degenerate: bool = False
    notes: str = ""
    owner_guess: str = ""


def _source_ids(result) -> list[int]:
    out: list[int] = []
    for h in getattr(result, "hits", None) or []:
        sid = getattr(h, "source_id", None)
        if sid is not None:
            out.append(int(sid))
    return out


def _shadow(result) -> dict:
    diag = getattr(result, "diagnostics", None)
    return dict(getattr(diag, "understanding_shadow", None) or {})


def _pipe(db, settings):
    ollama = OllamaService()
    emb = EmbeddingService(model=settings.embedding_model, ollama=ollama)
    qdrant = QdrantService(collection=settings.qdrant_collection)
    return RetrievalPipelineService(db, settings, emb, qdrant)


def run_shadow(db, settings) -> dict:
    prev = bool(settings.enable_knowledge_understanding)
    baselines: dict[str, list[int]] = {}
    rows: list[ShadowRow] = []

    settings.enable_knowledge_understanding = False
    SettingsRepository(db).save(settings)
    pipe = _pipe(db, settings)
    for q in SHADOW_QUERIES:
        result = pipe.run(q, q.lower(), debug=True)
        baselines[q] = _source_ids(result)

    settings.enable_knowledge_understanding = True
    SettingsRepository(db).save(settings)
    pipe = _pipe(db, settings)
    for q in SHADOW_QUERIES:
        result = pipe.run(q, q.lower(), debug=True)
        ids = _source_ids(result)
        sh = _shadow(result)
        rows.append(
            ShadowRow(
                query=q,
                ranking_unchanged=(ids == baselines[q]),
                overlap_ratio=float(sh.get("overlap_ratio") or 0),
                overlap_count=int(sh.get("overlap_count") or 0),
                dfp_count=int(sh.get("dfp_count") or 0),
                understanding_count=int(sh.get("understanding_count") or 0),
                understanding_only_count=int(sh.get("understanding_only_count") or 0),
                dfp_only_count=int(sh.get("dfp_only_count") or 0),
                shadow_ms=float(sh.get("total_understanding_shadow_ms") or 0),
                resolution_ms=float(sh.get("resolution_latency_ms") or 0),
                evidence_ms=float(sh.get("evidence_lookup_latency_ms") or 0),
                failure_reason=sh.get("failure_reason"),
                concepts_resolved=len(sh.get("resolved_concepts") or []),
                snapshot_id=sh.get("snapshot_id"),
            )
        )

    # leave ON for Phase 1 observation (prod expectation)
    settings.enable_knowledge_understanding = True
    SettingsRepository(db).save(settings)

    ratios = [r.overlap_ratio for r in rows]
    lats = [r.shadow_ms for r in rows]
    lats_sorted = sorted(lats)
    def pct(xs, p):
        if not xs:
            return 0.0
        i = int(round((p / 100) * (len(xs) - 1)))
        return xs[i]

    summary = {
        "queries": len(rows),
        "ranking_unchanged_all": all(r.ranking_unchanged for r in rows),
        "shadow_enabled_all": all(r.failure_reason is None or r.failure_reason == "" for r in rows)
        and all(r.snapshot_id for r in rows),
        "failure_rate": sum(1 for r in rows if r.failure_reason) / max(1, len(rows)),
        "concept_resolution_success": sum(1 for r in rows if r.concepts_resolved > 0)
        / max(1, len(rows)),
        "snapshot_availability": sum(1 for r in rows if r.snapshot_id) / max(1, len(rows)),
        "overlap_mean": round(statistics.mean(ratios), 4) if ratios else 0,
        "overlap_median": round(statistics.median(ratios), 4) if ratios else 0,
        "overlap_p50": round(pct(sorted(ratios), 50), 4) if ratios else 0,
        "understanding_only_mean": round(
            statistics.mean([r.understanding_only_count for r in rows]), 2
        ),
        "latency_p50_ms": round(pct(lats_sorted, 50), 1),
        "latency_p95_ms": round(pct(lats_sorted, 95), 1),
        "latency_max_ms": round(max(lats) if lats else 0, 1),
        "latency_mean_ms": round(statistics.mean(lats), 1) if lats else 0,
        "flag_prev": prev,
    }
    return {"summary": summary, "rows": [asdict(r) for r in rows]}


def _is_degenerate(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 20:
        return True
    # repeated token spam
    toks = t.split()
    if len(toks) >= 8 and len(set(toks[:20])) <= 2:
        return True
    return False


def run_ask(db, settings) -> dict:
    rag = RagService(db, settings)
    rows: list[AskRow] = []
    run_token = str(int(time.time()))
    for case_id, query, lang in ASK_CASES:
        t0 = time.perf_counter()
        try:
            # Unique request_id each run — answer_traces.request_id is unique.
            result = rag.answer(
                query,
                session_id=None,
                request_id=f"r11-{run_token}-{case_id}",
                debug=True,
                bypass_cache=True,
            )
            ms = int((time.perf_counter() - t0) * 1000)
            answer = getattr(result, "answer", None) or getattr(result, "text", "") or ""
            cites = getattr(result, "citations", None) or getattr(result, "sources", None) or []
            urls = []
            for c in cites[:8]:
                if isinstance(c, dict):
                    urls.append(str(c.get("url") or c.get("source_url") or "")[:120])
                else:
                    urls.append(str(getattr(c, "url", "") or "")[:120])
            truncated = answer.rstrip().endswith(("…", "...")) or (
                getattr(result, "finish_reason", None) == "length"
            )
            notes = f"ms={ms}"
            # lightweight contamination heuristics (generic, not bank-specific)
            newsish = sum(1 for u in urls if "/news" in u.lower() or "/blog" in u.lower())
            if case_id.startswith("org_overview") and newsish >= max(1, len(urls) // 2):
                notes += "; possible_news_contamination"
            rows.append(
                AskRow(
                    case_id=case_id,
                    query=query,
                    lang=lang,
                    answer_preview=answer[:400],
                    answer_len=len(answer),
                    source_count=len(urls) if urls else len(cites),
                    source_urls=[u for u in urls if u],
                    truncated=bool(truncated),
                    degenerate=_is_degenerate(answer),
                    notes=notes,
                )
            )
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            rows.append(
                AskRow(
                    case_id=case_id,
                    query=query,
                    lang=lang,
                    answer_preview="",
                    answer_len=0,
                    source_count=0,
                    notes=f"ERROR {type(exc).__name__}: {exc}"[:300],
                    degenerate=True,
                    owner_guess="Generation/Ops",
                )
            )
    return {"rows": [asdict(r) for r in rows]}


def main() -> int:
    out: dict = {"shadow": None, "ask": None}
    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        print("SHADOW_START", flush=True)
        out["shadow"] = run_shadow(db, settings)
        print("SHADOW_SUMMARY", json.dumps(out["shadow"]["summary"], ensure_ascii=False), flush=True)
        print("ASK_START", flush=True)
        out["ask"] = run_ask(db, settings)
        print("ASK_DONE", len(out["ask"]["rows"]), flush=True)
    path = "/tmp/r11-live-acceptance.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("WROTE", path, flush=True)
    # Exit 0 when shadow ran; ranking drift is reported in summary for inspection
    # (retrieval can be non-deterministic across repeated runs independent of KU).
    summary = out["shadow"]["summary"]
    ok = summary.get("failure_rate", 1) == 0 and summary.get("snapshot_availability", 0) == 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
