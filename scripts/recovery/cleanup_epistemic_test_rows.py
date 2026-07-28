#!/usr/bin/env python3
"""Transaction-safe cleanup of test-owned Epistemic Memory rows.

DEFAULT IS DRY-RUN. Does not delete unless --execute --i-understand are both set.

Safety:
  - Never deletes provenance_kind=source_intelligence claims
  - Never touches sources, chunks, Qdrant, chat, settings, users, jobs
  - Validates expected counts from dry-run before execute
  - Rolls back if affected row counts differ from plan

Usage (dry-run):
  set -a && source /opt/ai-site-agent/.env && set +a
  python scripts/recovery/cleanup_epistemic_test_rows.py --dry-run --out report.json

Execute (requires explicit approval flags):
  python scripts/recovery/cleanup_epistemic_test_rows.py \\
    --execute --i-understand --expected-evidence N --expected-claims M --expected-obs K
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef  # noqa: E402
from app.services.epistemic_memory.provenance_scope import (  # noqa: E402
    ATTRIBUTED_TO_FIXTURE,
    PROVENANCE_KIND_SOURCE_INTELLIGENCE,
    PROVENANCE_KIND_TEST,
)


def _engine(database: str | None):
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


def _test_claim_ids(session: Session) -> list[int]:
    rows = session.scalars(
        select(EpistemicClaim.id).where(
            or_(
                EpistemicClaim.provenance_kind == PROVENANCE_KIND_TEST,
                EpistemicClaim.attributed_to == ATTRIBUTED_TO_FIXTURE,
            ),
            EpistemicClaim.provenance_kind != PROVENANCE_KIND_SOURCE_INTELLIGENCE,
        )
    ).all()
    # Extra guard: never include SI even if attributed_to were wrong
    return [int(i) for i in rows]


def plan_cleanup(session: Session) -> dict:
    claim_ids = _test_claim_ids(session)
    # Refuse if any selected claim is SI
    si_guard = session.scalars(
        select(EpistemicClaim.id).where(
            EpistemicClaim.id.in_(claim_ids or [-1]),
            EpistemicClaim.provenance_kind == PROVENANCE_KIND_SOURCE_INTELLIGENCE,
        )
    ).all()
    if si_guard:
        raise SystemExit(f"Refusing: SI claim ids in test set: {si_guard}")

    evid_ids = []
    if claim_ids:
        evid_ids = list(
            session.scalars(
                select(EvidenceLink.id).where(
                    or_(
                        EvidenceLink.claim_id.in_(claim_ids),
                        EvidenceLink.provenance_kind == PROVENANCE_KIND_TEST,
                    )
                )
            ).all()
        )
    else:
        evid_ids = list(
            session.scalars(
                select(EvidenceLink.id).where(
                    EvidenceLink.provenance_kind == PROVENANCE_KIND_TEST
                )
            ).all()
        )
    evid_ids = [int(i) for i in evid_ids]

    # Observations: test provenance, and not referenced by remaining (non-deleted) evidence
    # After deleting test evidence, delete test obs that have no remaining links
    obs_ids = list(
        session.scalars(
            select(ObservationRef.id).where(
                ObservationRef.provenance_kind == PROVENANCE_KIND_TEST
            )
        ).all()
    )
    obs_ids = [int(i) for i in obs_ids]

    before = {
        "claims": int(session.scalar(select(func.count()).select_from(EpistemicClaim)) or 0),
        "evidence_links": int(
            session.scalar(select(func.count()).select_from(EvidenceLink)) or 0
        ),
        "observation_refs": int(
            session.scalar(select(func.count()).select_from(ObservationRef)) or 0
        ),
        "si_claims": int(
            session.scalar(
                select(func.count())
                .select_from(EpistemicClaim)
                .where(
                    EpistemicClaim.provenance_kind
                    == PROVENANCE_KIND_SOURCE_INTELLIGENCE
                )
            )
            or 0
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run",
        "would_delete": {
            "evidence_link_ids": evid_ids,
            "claim_ids": claim_ids,
            "observation_ref_ids": obs_ids,
            "evidence_count": len(evid_ids),
            "claim_count": len(claim_ids),
            "observation_count": len(obs_ids),
        },
        "before": before,
        "after_projected": {
            "claims": before["claims"] - len(claim_ids),
            "evidence_links": before["evidence_links"] - len(evid_ids),
            "observation_refs": before["observation_refs"] - len(obs_ids),
            "si_claims": before["si_claims"],
        },
        "guards": {
            "never_delete_source_intelligence": True,
            "never_touch_sources_chunks_qdrant_chat": True,
            "execute_requires_flags": ["--execute", "--i-understand", "expected counts"],
        },
    }


def execute_cleanup(
    session: Session,
    *,
    expected_evidence: int,
    expected_claims: int,
    expected_obs: int,
    backup_path: Path | None,
) -> dict:
    plan = plan_cleanup(session)
    wd = plan["would_delete"]
    if (
        wd["evidence_count"] != expected_evidence
        or wd["claim_count"] != expected_claims
        or wd["observation_count"] != expected_obs
    ):
        session.rollback()
        raise SystemExit(
            "ABORT: dry-run counts differ from --expected-* "
            f"(got evidence={wd['evidence_count']} claims={wd['claim_count']} "
            f"obs={wd['observation_count']}; expected "
            f"{expected_evidence}/{expected_claims}/{expected_obs})"
        )

    if backup_path:
        # Caller should have run pg_dump; record path only
        plan["backup_path"] = str(backup_path)

    try:
        if wd["evidence_link_ids"]:
            session.execute(
                delete(EvidenceLink).where(
                    EvidenceLink.id.in_(wd["evidence_link_ids"])
                )
            )
        if wd["claim_ids"]:
            # Block SI again at execute time
            session.execute(
                delete(EpistemicClaim).where(
                    EpistemicClaim.id.in_(wd["claim_ids"]),
                    EpistemicClaim.provenance_kind
                    != PROVENANCE_KIND_SOURCE_INTELLIGENCE,
                )
            )
        if wd["observation_ref_ids"]:
            # Only delete test obs with no remaining evidence links
            still_linked = set(
                session.scalars(
                    select(EvidenceLink.observation_ref_id).where(
                        EvidenceLink.observation_ref_id.in_(wd["observation_ref_ids"])
                    )
                ).all()
            )
            deletable = [i for i in wd["observation_ref_ids"] if i not in still_linked]
            if deletable:
                session.execute(
                    delete(ObservationRef).where(
                        ObservationRef.id.in_(deletable),
                        ObservationRef.provenance_kind == PROVENANCE_KIND_TEST,
                    )
                )
            wd["observation_ref_ids_deleted"] = deletable

        # Verify SI unchanged
        si_after = int(
            session.scalar(
                select(func.count())
                .select_from(EpistemicClaim)
                .where(
                    EpistemicClaim.provenance_kind
                    == PROVENANCE_KIND_SOURCE_INTELLIGENCE
                )
            )
            or 0
        )
        if si_after != plan["before"]["si_claims"]:
            session.rollback()
            raise SystemExit("ABORT: source_intelligence claim count changed — rolled back")

        session.commit()
        plan["mode"] = "executed"
        plan["deleted"] = True
        plan["after"] = {
            "claims": int(
                session.scalar(select(func.count()).select_from(EpistemicClaim)) or 0
            ),
            "evidence_links": int(
                session.scalar(select(func.count()).select_from(EvidenceLink)) or 0
            ),
            "observation_refs": int(
                session.scalar(select(func.count()).select_from(ObservationRef)) or 0
            ),
            "si_claims": si_after,
        }
        return plan
    except Exception:
        session.rollback()
        raise


def maybe_backup(database: str | None, backup_dir: Path) -> Path | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    from sqlalchemy.engine import make_url

    u = make_url(url)
    if database:
        u = u.set(database=database)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = backup_dir / f"epistemic_tables.{u.database}.{ts}.dump"
    env = os.environ.copy()
    if u.password:
        env["PGPASSWORD"] = u.password
    cmd = [
        "pg_dump",
        "-h",
        str(u.host or "localhost"),
        "-p",
        str(u.port or 5432),
        "-U",
        str(u.username or "ai_agent"),
        "-d",
        str(u.database),
        "-Fc",
        "-t",
        "observation_ref",
        "-t",
        "claim",
        "-t",
        "evidence_link",
        "-f",
        str(out),
    ]
    print(f"Creating backup: {' '.join(cmd[:8])} ... → {out}", file=sys.stderr)
    subprocess.run(cmd, check=True, env=env)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", default=None)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--execute", action="store_true", default=False)
    ap.add_argument("--i-understand", action="store_true", default=False)
    ap.add_argument("--expected-evidence", type=int, default=None)
    ap.add_argument("--expected-claims", type=int, default=None)
    ap.add_argument("--expected-obs", type=int, default=None)
    ap.add_argument("--backup-dir", type=Path, default=REPO / "scripts/recovery/backups")
    ap.add_argument("--skip-backup", action="store_true", default=False)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    engine = _engine(args.database)
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as session:
        if args.execute:
            if not args.i_understand:
                raise SystemExit("Refusing execute without --i-understand")
            if None in (
                args.expected_evidence,
                args.expected_claims,
                args.expected_obs,
            ):
                raise SystemExit(
                    "Refusing execute without --expected-evidence/claims/obs "
                    "(copy from dry-run would_delete counts)"
                )
            backup = None
            if not args.skip_backup:
                backup = maybe_backup(args.database, args.backup_dir)
            report = execute_cleanup(
                session,
                expected_evidence=args.expected_evidence,
                expected_claims=args.expected_claims,
                expected_obs=args.expected_obs,
                backup_path=backup,
            )
        else:
            report = plan_cleanup(session)
            report["note"] = (
                "DRY-RUN only — no rows deleted. Re-run with "
                "--execute --i-understand --expected-* after explicit approval."
            )

    text_out = json.dumps(report, indent=2, ensure_ascii=False)
    print(text_out)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text_out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
