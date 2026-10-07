#!/usr/bin/env python3
"""Wave B — controlled SI rules-only upgrade to current profile version + KU rebuild.

Runs against the live DATABASE_URL using the workspace code tree (so SI fixes
apply before a full redeploy). Disables Memory shadow writes for the bulk pass
to avoid long-lived settings-row locks under multi-worker SI.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import text

from app.core.database import SessionLocal
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_understanding.store import UnderstandingStore
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_generation_service import (
    IntelligenceOptions,
    SourceIntelligenceGenerationService,
)


def main() -> int:
    with SessionLocal() as db:
        db.execute(
            text(
                "update index_jobs set status='stopped', current_phase='stopped', "
                "finished_at=now(), updated_at=now() where status='running'"
            )
        )
        db.commit()

        settings = SettingsRepository(db).get_or_create()
        prev = {
            "llm": bool(getattr(settings, "enable_llm_source_intelligence", True)),
            "shadow": bool(getattr(settings, "memory_shadow_write_enabled", True)),
            "canonical_shadow": bool(
                getattr(settings, "memory_canonical_shadow_enabled", True)
            ),
            "workers": int(getattr(settings, "source_intelligence_worker_count", 0) or 0),
        }
        settings.enable_llm_source_intelligence = False
        settings.memory_shadow_write_enabled = False
        settings.memory_canonical_shadow_enabled = False
        settings.source_intelligence_worker_count = 1
        SettingsRepository(db).save(settings)
        print(f"FLAGS_PREV={prev} NOW llm=0 shadow=0 workers=1", flush=True)

        db.execute(
            text(
                "update sources set needs_intelligence=true "
                "where status='indexed' and coalesce(profile_version,'') <> :v"
            ),
            {"v": SOURCE_INTELLIGENCE_VERSION},
        )
        db.execute(
            text(
                """
                update sources set needs_intelligence=true
                where status='indexed'
                  and (
                    url ~* '/news(?:-post)?(/|$)'
                    or url ~* '/blog(/|$)'
                    or url ~* '/campaign|/promo'
                  )
                  and (
                    coalesce(document_type,'') not in (
                      'news_page','blog_page','blog_post',
                      'campaign_page','promotion_page','offer_page','action_page'
                    )
                    or coalesce(page_role,'') in (
                      'organization_overview','service_overview'
                    )
                    or canonical is true
                  )
                """
            )
        )
        db.commit()
        needs = db.execute(
            text(
                "select count(*) from sources "
                "where status='indexed' and needs_intelligence=true"
            )
        ).scalar()
        print(
            f"NEEDS={needs} KV={KnowledgeVersionService(db).get()} "
            f"TARGET={SOURCE_INTELLIGENCE_VERSION}",
            flush=True,
        )

    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        svc = SourceIntelligenceGenerationService(db, settings)

        def tick(phase: str, message: str, extra: dict) -> None:
            processed = int(extra.get("processed") or extra.get("updated") or 0)
            selected = int(extra.get("selected_sources") or extra.get("selected") or 0)
            if (
                processed % 25 == 0
                or phase
                in {
                    "finalize",
                    "completed",
                    "invalidating_cache",
                    "rebuilding_understanding",
                    "analyzing_sources",
                }
            ):
                print(
                    f"PROGRESS {phase} {processed}/{selected} {message[:140]}",
                    flush=True,
                )

        opts = IntelligenceOptions(scope="needs_intelligence", generate_summaries=True)
        result = svc.run(opts, on_progress=tick)
        print("RESULT", result, flush=True)

        settings = SettingsRepository(db).get_or_create()
        settings.enable_llm_source_intelligence = True
        settings.memory_shadow_write_enabled = True
        settings.memory_canonical_shadow_enabled = True
        settings.source_intelligence_worker_count = prev["workers"]
        SettingsRepository(db).save(settings)
        print("FLAGS_RESTORED llm=1 shadow=1", flush=True)

        versions = db.execute(
            text(
                "select coalesce(profile_version,''), count(*) "
                "from sources where status='indexed' group by 1 order by 2 desc"
            )
        ).all()
        print("VERSIONS", versions, flush=True)
        snaps = db.execute(
            text(
                "select id, status, knowledge_version, concept_count, evidence_count, "
                "left(coalesce(error_message,''), 240) "
                "from understanding_snapshots order by id"
            )
        ).all()
        print("SNAPSHOTS", snaps, flush=True)
        print("KV", KnowledgeVersionService(db).get(), flush=True)
        ready = UnderstandingStore(db).latest_ready()
        print(
            "READY",
            None
            if ready is None
            else {
                "id": ready.id,
                "kv": ready.knowledge_version,
                "concepts": ready.concept_count,
                "evidence": ready.evidence_count,
            },
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
