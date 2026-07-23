"""RFC-100 Step 027 — Epistemic Memory schema tests (inactive tables)."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from app.models.epistemic_memory import EpistemicClaim, EvidenceLink, ObservationRef
from tests._dbutil import is_usable_postgres_test_url

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0014_epistemic_memory_tables.py"
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
EPISTEMIC_MODEL_ALLOWLIST = frozenset(
    {
        "models/epistemic_memory.py",
        "models/__init__.py",
    }
)
EPISTEMIC_SERVICE_PREFIX = "services/epistemic_memory/"
EPISTEMIC_WRITE_ALLOWLIST = frozenset(
    {
        "services/epistemic_memory/epistemic_memory_service.py",
        "services/epistemic_memory/epistemic_memory_write_service.py",
    }
)
EPISTEMIC_WRITE_TOKENS = (
    "ObservationRef(",
    "EpistemicClaim(",
    "EvidenceLink(",
    "from app.models.epistemic_memory",
)


def _postgres_session(*, fresh: bool = False):
    from tests._dbutil import make_engine

    engine = make_engine(fresh=fresh)
    return sessionmaker(bind=engine)(), engine


@pytest.mark.unit
def test_postgres_test_url_rejects_doc_placeholder():
    assert not is_usable_postgres_test_url("postgresql+psycopg://...")
    assert not is_usable_postgres_test_url("")
    assert is_usable_postgres_test_url(
        "postgresql+psycopg://ai_agent:secret@127.0.0.1:5432/ai_site_agent_test"
    )


@pytest.mark.unit
def test_migration_0014_chain_and_tables():
    spec = importlib.util.spec_from_file_location("migration_0014", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0014_epistemic_memory_tables"
    assert module.down_revision == "0013_cache_namespace_v2_enabled"
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    for table in ("observation_ref", "claim", "evidence_link"):
        assert f'"{table}"' in source
    assert "def upgrade" in source
    assert "def downgrade" in source


@pytest.mark.unit
def test_observation_ref_table_and_immutability_columns():
    mapper = inspect(ObservationRef)
    col_names = {c.key for c in mapper.columns}
    assert col_names >= {
        "id",
        "source_id",
        "chunk_id",
        "observation_key",
        "content_hash",
        "excerpt",
        "observed_at",
        "provenance_kind",
        "provenance_ref",
        "extraction_version",
        "created_at",
    }
    assert "updated_at" not in col_names
    assert mapper.columns["observation_key"].unique is True
    assert mapper.columns["provenance_kind"].nullable is False


@pytest.mark.unit
def test_claim_table_requires_attribution_and_provenance():
    mapper = inspect(EpistemicClaim)
    col_names = {c.key for c in mapper.columns}
    assert col_names >= {
        "id",
        "proposition",
        "scope_json",
        "epistemic_status",
        "attributed_to",
        "provenance_kind",
        "provenance_ref",
        "confidence",
        "superseded_by_id",
        "revision_of_id",
        "created_at",
        "updated_at",
    }
    for required in ("proposition", "attributed_to", "provenance_kind"):
        assert mapper.columns[required].nullable is False
    assert mapper.columns["epistemic_status"].default.arg == "provisional"


@pytest.mark.unit
def test_evidence_link_references_claim_and_observation():
    mapper = inspect(EvidenceLink)
    col_names = {c.key for c in mapper.columns}
    assert col_names >= {
        "id",
        "claim_id",
        "observation_ref_id",
        "role",
        "provenance_kind",
        "provenance_ref",
        "link_confidence",
        "created_at",
    }
    claim_fk = mapper.columns["claim_id"].foreign_keys
    obs_fk = mapper.columns["observation_ref_id"].foreign_keys
    assert any(fk.target_fullname == "claim.id" for fk in claim_fk)
    assert any(fk.target_fullname == "observation_ref.id" for fk in obs_fk)
    assert mapper.columns["role"].nullable is False
    assert mapper.columns["provenance_kind"].nullable is False


@pytest.mark.unit
def test_observation_ref_immutable_row_has_no_updated_at():
    """Observations are append-only references — only created_at is stored."""
    session, engine = _postgres_session()
    try:
        obs = ObservationRef(
            observation_key="obs:test:1",
            content_hash="abc123",
            observed_at=datetime.now(timezone.utc),
            provenance_kind="index_extraction",
            provenance_ref="job:1",
            excerpt="Sample excerpt",
        )
        session.add(obs)
        session.commit()
        session.refresh(obs)
        assert obs.id is not None
        assert obs.created_at is not None
        assert "updated_at" not in inspect(ObservationRef).columns.keys()
        session.delete(obs)
        session.commit()
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_claim_and_evidence_link_roundtrip():
    session, engine = _postgres_session()
    try:
        obs = ObservationRef(
            observation_key="obs:test:2",
            content_hash="def456",
            observed_at=datetime.now(timezone.utc),
            provenance_kind="si_extraction",
            provenance_ref="si:42",
        )
        claim = EpistemicClaim(
            proposition="The homepage lists three products.",
            scope_json='{"region":"products"}',
            attributed_to="claim_extraction",
            provenance_kind="si_extraction",
            provenance_ref="si:42",
            confidence=0.82,
        )
        session.add(obs)
        session.add(claim)
        session.flush()
        link = EvidenceLink(
            claim_id=claim.id,
            observation_ref_id=obs.id,
            role="support",
            provenance_kind="si_extraction",
            provenance_ref="si:42",
            link_confidence=0.9,
        )
        session.add(link)
        session.commit()
        assert link.id is not None
        assert link.claim_id == claim.id
        assert link.observation_ref_id == obs.id
        session.delete(link)
        session.delete(claim)
        session.delete(obs)
        session.commit()
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_negative_no_production_writes_to_epistemic_tables():
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel.startswith("migrations/"):
            continue
        if rel in EPISTEMIC_MODEL_ALLOWLIST:
            continue
        if rel.startswith(EPISTEMIC_SERVICE_PREFIX):
            if rel in EPISTEMIC_WRITE_ALLOWLIST:
                continue
            continue
        source = path.read_text(encoding="utf-8")
        for token in EPISTEMIC_WRITE_TOKENS:
            if token in source:
                violations.append(f"{rel}: {token}")
    assert violations == []
