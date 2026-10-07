#!/usr/bin/env python3
"""Wave B — simple sequential SI rules upgrade + KU rebuild.

Avoids SourceIntelligenceGenerationService.run() thread/pool hang observed
under this host. One DB session per batch; commit every BATCH sources.
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.knowledge_understanding.rebuild import UnderstandingRebuildService
from app.services.knowledge_understanding.store import UnderstandingStore
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_service import SourceIntelligenceService

BATCH = 50


def _mark_needs(db) -> int:
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
    return int(
        db.execute(
            text(
                "select count(*) from sources "
                "where status='indexed' and needs_intelligence=true"
            )
        ).scalar()
        or 0
    )


def main() -> int:
    ku_only = "--ku-only" in sys.argv
    errors = 0

    if not ku_only:
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
                "llm": bool(settings.enable_llm_source_intelligence),
                "shadow": bool(settings.memory_shadow_write_enabled),
                "canonical_shadow": bool(settings.memory_canonical_shadow_enabled),
            }
            settings.enable_llm_source_intelligence = False
            settings.memory_shadow_write_enabled = False
            settings.memory_canonical_shadow_enabled = False
            SettingsRepository(db).save(settings)
            print(f"FLAGS_PREV={prev} NOW llm=0 shadow=0", flush=True)
            needs = _mark_needs(db)
            print(
                f"NEEDS={needs} KV={KnowledgeVersionService(db).get()} "
                f"TARGET={SOURCE_INTELLIGENCE_VERSION}",
                flush=True,
            )

        processed = 0
        updated = 0
        t0 = time.monotonic()

        while True:
            with SessionLocal() as db:
                settings = SettingsRepository(db).get_or_create()
                profile = KnowledgeProfileService.from_settings(settings)
                ids = list(
                    db.execute(
                        text(
                            "select id from sources "
                            "where status='indexed' and needs_intelligence=true "
                            "order by id limit :lim"
                        ),
                        {"lim": BATCH},
                    ).scalars()
                )
                if not ids:
                    print("BATCH_EMPTY", flush=True)
                    break
                sources = {
                    int(s.id): s
                    for s in db.scalars(select(Source).where(Source.id.in_(ids))).all()
                }
                for sid in ids:
                    src = sources.get(int(sid))
                    if src is None:
                        continue
                    try:
                        sp = SourceIntelligenceService.build_profile(
                            src,
                            profile,
                            settings=settings,
                            use_llm=False,
                            db=db,
                        )
                        SourceIntelligenceService.apply_to_source(
                            src, sp, settings=settings
                        )
                        src.needs_intelligence = False
                        updated += 1
                    except Exception as exc:  # noqa: BLE001
                        errors += 1
                        print(f"ERR sid={sid} {type(exc).__name__}: {exc}", flush=True)
                        db.rollback()
                        settings = SettingsRepository(db).get_or_create()
                        profile = KnowledgeProfileService.from_settings(settings)
                        continue
                    processed += 1
                db.commit()
                elapsed = time.monotonic() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                print(
                    f"PROGRESS {processed} updated={updated} errors={errors} "
                    f"rate={rate:.1f}/s last_id={ids[-1]}",
                    flush=True,
                )

        print("SI_PASS_DONE", flush=True)
    else:
        print("KU_ONLY mode — skipping SI pass", flush=True)

    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        kv = KnowledgeVersionService(db).bump()
        print(f"KU_REBUILD_START kv={kv}", flush=True)

        def tick(phase: str, message: str, extra: dict) -> None:
            print(f"KU {phase} {message[:140]} {extra}", flush=True)

        snap_id = UnderstandingRebuildService(db, settings).rebuild_after_si(
            on_progress=tick
        )
        print("KU_REBUILD_RESULT", snap_id, flush=True)

        settings.enable_llm_source_intelligence = True
        settings.memory_shadow_write_enabled = True
        settings.memory_canonical_shadow_enabled = True
        SettingsRepository(db).save(settings)
        print("FLAGS_RESTORED", flush=True)

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
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
