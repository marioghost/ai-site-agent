#!/usr/bin/env python3
"""Read-only inventory of test-owned Epistemic Memory rows (demo readiness).

Does NOT delete or modify data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef  # noqa: E402
from app.services.epistemic_memory import EpistemicMemoryService  # noqa: E402
from app.services.epistemic_memory.provenance_scope import (  # noqa: E402
    ATTRIBUTED_TO_FIXTURE,
    PROVENANCE_KIND_SOURCE_INTELLIGENCE,
    PROVENANCE_KIND_TEST,
    ProvenanceScope,
    claim_sql_filter,
    is_test_claim,
)
from app.services.tension_surfacing import TensionSurfacingService  # noqa: E402


def _engine_from_env(database: str | None):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    if database:
        from sqlalchemy.engine import make_url

        u = make_url(url).set(database=database)
        url = u.render_as_string(hide_password=False)
        if "+psycopg" in os.environ["DATABASE_URL"] and url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return create_engine(url, future=True)


def _claim_counts(session: Session, scope: ProvenanceScope) -> dict:
    filt = claim_sql_filter(scope)
    total_q = select(func.count()).select_from(EpistemicClaim)
    active_q = select(func.count()).select_from(EpistemicClaim).where(
        EpistemicClaim.superseded_by_id.is_(None)
    )
    if filt is not None:
        total_q = total_q.where(filt)
        active_q = active_q.where(filt)
    total = int(session.scalar(total_q) or 0)
    active = int(session.scalar(active_q) or 0)
    return {
        "claims": total,
        "active_claims": active,
        "superseded_claims": total - active,
    }


def audit(session: Session) -> dict:
    test_claims = list(
        session.scalars(
            select(EpistemicClaim)
            .where(
                or_(
                    EpistemicClaim.provenance_kind == PROVENANCE_KIND_TEST,
                    EpistemicClaim.attributed_to == ATTRIBUTED_TO_FIXTURE,
                )
            )
            .order_by(EpistemicClaim.id)
        ).all()
    )
    test_claim_ids = [c.id for c in test_claims]

    test_obs = list(
        session.scalars(
            select(ObservationRef)
            .where(ObservationRef.provenance_kind == PROVENANCE_KIND_TEST)
            .order_by(ObservationRef.id)
        ).all()
    )
    test_obs_ids = [o.id for o in test_obs]

    if test_claim_ids:
        test_evidence = list(
            session.scalars(
                select(EvidenceLink)
                .where(
                    or_(
                        EvidenceLink.provenance_kind == PROVENANCE_KIND_TEST,
                        EvidenceLink.claim_id.in_(test_claim_ids),
                    )
                )
                .order_by(EvidenceLink.id)
            ).all()
        )
    else:
        test_evidence = list(
            session.scalars(
                select(EvidenceLink)
                .where(EvidenceLink.provenance_kind == PROVENANCE_KIND_TEST)
                .order_by(EvidenceLink.id)
            ).all()
        )
    test_evidence_ids = [e.id for e in test_evidence]

    chains = []
    for e in test_evidence:
        claim = session.get(EpistemicClaim, e.claim_id)
        obs = session.get(ObservationRef, e.observation_ref_id)
        chains.append(
            {
                "evidence_link_id": e.id,
                "evidence_provenance_kind": e.provenance_kind,
                "role": e.role,
                "claim_id": e.claim_id,
                "claim_provenance_kind": claim.provenance_kind if claim else None,
                "claim_attributed_to": claim.attributed_to if claim else None,
                "observation_ref_id": e.observation_ref_id,
                "observation_provenance_kind": obs.provenance_kind if obs else None,
                "safe_to_delete_with_test_cleanup": bool(
                    claim
                    and is_test_claim(
                        provenance_kind=claim.provenance_kind,
                        attributed_to=claim.attributed_to,
                    )
                ),
            }
        )

    linked_obs = {e.observation_ref_id for e in test_evidence}
    orphan_test_obs = [oid for oid in test_obs_ids if oid not in linked_obs]

    memory = EpistemicMemoryService(session)
    surfacing = TensionSurfacingService(memory)
    all_tensions = surfacing.surface_tensions(
        claim_limit=500, provenance_scope=ProvenanceScope.ALL
    )
    real_tensions = surfacing.surface_tensions(
        claim_limit=500, provenance_scope=ProvenanceScope.REAL
    )
    test_tensions = surfacing.surface_tensions(
        claim_limit=500, provenance_scope=ProvenanceScope.TEST
    )

    real = _claim_counts(session, ProvenanceScope.REAL)
    test = _claim_counts(session, ProvenanceScope.TEST)
    si_count = int(
        session.scalar(
            select(func.count())
            .select_from(EpistemicClaim)
            .where(
                EpistemicClaim.provenance_kind == PROVENANCE_KIND_SOURCE_INTELLIGENCE
            )
        )
        or 0
    )
    real_obs = int(
        session.scalar(
            select(func.count())
            .select_from(ObservationRef)
            .where(ObservationRef.provenance_kind != PROVENANCE_KIND_TEST)
        )
        or 0
    )
    real_evid = int(
        session.scalar(
            select(func.count())
            .select_from(EvidenceLink)
            .where(EvidenceLink.provenance_kind != PROVENANCE_KIND_TEST)
        )
        or 0
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "deleted": False,
        "test_inventory": {
            "claims": {
                "count": len(test_claim_ids),
                "ids": test_claim_ids,
                "sample": [
                    {
                        "id": c.id,
                        "provenance_kind": c.provenance_kind,
                        "attributed_to": c.attributed_to,
                        "superseded_by_id": c.superseded_by_id,
                        "proposition": (c.proposition or "")[:80],
                    }
                    for c in test_claims[:15]
                ],
            },
            "observation_ref": {
                "count": len(test_obs_ids),
                "ids": test_obs_ids,
                "orphan_ids": orphan_test_obs,
            },
            "evidence_link": {
                "count": len(test_evidence_ids),
                "ids": test_evidence_ids,
            },
            "dependency_chains": chains,
            "derived_tensions": {
                "all": len(all_tensions),
                "test_scoped": len(test_tensions),
                "real_scoped": len(real_tensions),
                "test_examples": [
                    {
                        "type": t.tension_type,
                        "claim_ids": list(t.claim_ids),
                        "provenance_scope": t.provenance_scope,
                        "summary": t.summary[:160],
                    }
                    for t in test_tensions[:8]
                ],
            },
        },
        "real_only_operational": {
            **real,
            "observations": real_obs,
            "evidence_links": real_evid,
            "source_intelligence_claims": si_count,
            "support_deficit_tensions": sum(
                1 for t in real_tensions if t.tension_type == "support_deficit"
            ),
            "conflict_tensions": sum(
                1 for t in real_tensions if t.tension_type == "conflict"
            ),
            "open_tensions": len(real_tensions),
        },
        "test_only_operational": {
            **test,
            "observations": len(test_obs_ids),
            "evidence_links": len(test_evidence_ids),
            "open_tensions": len(test_tensions),
        },
        "cleanup_order_hint": [
            "1. Backup epistemic tables (pg_dump -t observation_ref -t claim -t evidence_link)",
            "2. DELETE evidence_link for test set",
            "3. DELETE claim for test set (never source_intelligence)",
            "4. DELETE observation_ref provenance_kind=test when unreferenced",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    engine = _engine_from_env(args.database)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as session:
        report = audit(session)
    text_out = json.dumps(report, indent=2, ensure_ascii=False)
    print(text_out)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text_out + "\n", encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
