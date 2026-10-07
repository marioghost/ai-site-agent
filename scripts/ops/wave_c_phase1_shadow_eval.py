#!/usr/bin/env python3
"""Wave C — Phase 1 Understanding shadow eval (observe-only, zero ranking)."""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.core.database import SessionLocal
from app.repositories.settings_repository import SettingsRepository
from app.services.embedding_service import EmbeddingService
from app.services.ollama_service import OllamaService
from app.services.qdrant_service import QdrantService
from app.services.retrieval_pipeline_service import RetrievalPipelineService

QUERIES = [
    "Що таке UKRSIBBANK?",
    "Як відкрити рахунок?",
    "Кредитна картка умови",
    "Відділення банку Київ",
    "Курси валют",
    "Мобільний банкінг",
]


def _source_ids(result) -> list[int]:
    out: list[int] = []
    for h in getattr(result, "hits", None) or []:
        sid = getattr(h, "source_id", None)
        if sid is not None:
            out.append(int(sid))
    return out


def _shadow(result) -> dict:
    diag = getattr(result, "diagnostics", None)
    sh = getattr(diag, "understanding_shadow", None) if diag is not None else None
    return dict(sh or {})


def _run_one(db, settings, message: str):
    ollama = OllamaService()
    emb = EmbeddingService(model=settings.embedding_model, ollama=ollama)
    qdrant = QdrantService(collection=settings.qdrant_collection)
    pipe = RetrievalPipelineService(db, settings, emb, qdrant)
    t0 = time.perf_counter()
    result = pipe.run(message, message.lower(), debug=True)
    ms = int((time.perf_counter() - t0) * 1000)
    return result, ms


def main() -> int:
    leave_on = "--leave-on" in sys.argv
    rows: list[dict] = []

    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        prev = bool(settings.enable_knowledge_understanding)
        print(f"FLAG_PREV={prev}", flush=True)

        # Baseline ranking with flag OFF
        settings.enable_knowledge_understanding = False
        SettingsRepository(db).save(settings)
        baselines: dict[str, list[int]] = {}
        for q in QUERIES:
            result, ms = _run_one(db, settings, q)
            baselines[q] = _source_ids(result)
            print(f"OFF {q!r} sources={baselines[q][:8]} ms={ms}", flush=True)

        # Shadow ON
        settings.enable_knowledge_understanding = True
        SettingsRepository(db).save(settings)
        print("FLAG_ON", flush=True)

        for q in QUERIES:
            result, ms = _run_one(db, settings, q)
            ids = _source_ids(result)
            sh = _shadow(result)
            same = ids == baselines[q]
            row = {
                "query": q,
                "pipeline_ms": ms,
                "ranking_unchanged": same,
                "baseline_source_ids": baselines[q],
                "on_source_ids": ids,
                "shadow": {
                    "enabled": sh.get("understanding_shadow_enabled"),
                    "snapshot_id": sh.get("snapshot_id"),
                    "kv": sh.get("knowledge_version"),
                    "overlap_ratio": sh.get("overlap_ratio"),
                    "overlap_count": sh.get("overlap_count"),
                    "dfp_count": sh.get("dfp_count"),
                    "understanding_count": sh.get("understanding_count"),
                    "total_ms": sh.get("total_understanding_shadow_ms"),
                    "resolution_ms": sh.get("resolution_latency_ms"),
                    "evidence_ms": sh.get("evidence_lookup_latency_ms"),
                    "failure_reason": sh.get("failure_reason"),
                    "why": (sh.get("why_summary") or "")[:200],
                    "concepts": sh.get("resolved_concepts") or [],
                },
            }
            rows.append(row)
            print(
                f"ON  {q!r} same={same} overlap={sh.get('overlap_ratio')} "
                f"shadow_ms={sh.get('total_understanding_shadow_ms')} "
                f"fail={sh.get('failure_reason')}",
                flush=True,
            )

        if not leave_on:
            settings.enable_knowledge_understanding = prev
            SettingsRepository(db).save(settings)
            print(f"FLAG_RESTORED={prev}", flush=True)
        else:
            print("FLAG_LEFT_ON=true", flush=True)

    unchanged = all(r["ranking_unchanged"] for r in rows)
    enabled_ok = all(r["shadow"]["enabled"] for r in rows)
    no_fail = all(not r["shadow"]["failure_reason"] for r in rows)
    summary = {
        "queries": len(rows),
        "ranking_unchanged_all": unchanged,
        "shadow_enabled_all": enabled_ok,
        "no_failure_all": no_fail,
        "avg_shadow_ms": round(
            sum(r["shadow"]["total_ms"] or 0 for r in rows) / max(1, len(rows)), 1
        ),
        "avg_overlap_ratio": round(
            sum(float(r["shadow"]["overlap_ratio"] or 0) for r in rows) / max(1, len(rows)),
            4,
        ),
    }
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    print("ROWS", json.dumps(rows, ensure_ascii=False, indent=2), flush=True)
    return 0 if unchanged and enabled_ok and no_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
