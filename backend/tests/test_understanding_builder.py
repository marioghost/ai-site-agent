"""Understanding Builder — SI → concepts + evidence links."""
from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.settings import Settings
from app.models.source import Source
from app.services.knowledge_understanding.adapters.concept_index import (
    ConceptIndexUnderstandingLayer,
)
from app.services.knowledge_understanding.builder import (
    UnderstandingBuilder,
    extract_raw_concepts,
)
from app.services.knowledge_understanding.rebuild import UnderstandingRebuildService
from tests._dbutil import make_engine


def _hash_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic pseudo-embeddings: similar strings → similar vectors."""
    out: list[list[float]] = []
    for text in texts:
        norm = " ".join((text or "").lower().split())
        vec = [0.0] * 32
        if not norm:
            out.append(vec)
            continue
        for i, ch in enumerate(norm[:64]):
            vec[i % 32] += (ord(ch) % 31) / 31.0
        for i in range(len(norm) - 1):
            bigram = ord(norm[i]) * 31 + ord(norm[i + 1])
            vec[bigram % 32] += 0.35
        n = sum(v * v for v in vec) ** 0.5 or 1.0
        out.append([v / n for v in vec])
    return out


def _make_source(
    *,
    url: str,
    title: str,
    main_topic: str,
    subtopics: list[str] | None = None,
    keywords: list[str] | None = None,
    canonical: bool = False,
    content_hash: str | None = None,
    entity_type: str = "",
    entity_conf: float = 0.0,
) -> Source:
    semantic = {
        "main_topic": main_topic,
        "main_topic_confidence": 0.9,
        "subtopics": subtopics or [],
        "search_keywords": keywords or [],
        "synonyms": [],
        "semantic_tags": [],
        "suitable_for": ["documentation"],
        "supported_intents": ["specific_fact"],
        "entity_type": entity_type,
        "entity_type_confidence": entity_conf,
        "confidence": 0.85,
        "generator": "test",
    }
    return Source(
        source_type="page",
        url=url,
        title=title,
        status="indexed",
        canonical=canonical,
        content_hash=content_hash,
        intelligence_json=json.dumps(semantic),
        profile_version="test",
    )


@pytest.fixture()
def db_session_kul():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    settings = Settings(id=1, llm_model="test-model", knowledge_version=1)
    session.add(settings)
    session.commit()
    try:
        yield session, settings
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
def test_extract_main_topic_and_subtopics():
    src = _make_source(
        url="https://corp.example/about",
        title="About",
        main_topic="Company overview",
        subtopics=["Leadership", "History"],
        keywords=["about us"],
    )
    src.id = 1
    raw = extract_raw_concepts(src)
    labels = {r.label for r in raw}
    assert "Company overview" in labels
    assert "Leadership" in labels
    assert "History" in labels
    assert any(r.relation == "explains" for r in raw)


@pytest.mark.unit
def test_need_types_are_not_concept_aliases():
    src = _make_source(
        url="https://docs.example/guide",
        title="Guide",
        main_topic="Product guide",
        keywords=["guide"],
    )
    src.id = 7
    raw = extract_raw_concepts(src)
    main = next(r for r in raw if r.label == "Product guide")
    alias_l = {a.lower() for a in main.aliases}
    assert "documentation" not in alias_l
    assert "specific_fact" not in alias_l
    assert "guide" in alias_l


@pytest.mark.unit
def test_entity_uses_entity_type_not_page_title():
    src = _make_source(
        url="https://corp.example/widget",
        title="Home | Acme Corp",
        main_topic="Widgets",
        entity_type="product",
        entity_conf=0.8,
    )
    src.id = 9
    raw = extract_raw_concepts(src)
    entities = [r for r in raw if r.is_entity]
    assert len(entities) == 1
    assert entities[0].label == "product"
    assert "Home | Acme Corp" in entities[0].aliases


@pytest.mark.unit
def test_concept_index_satisfies_protocol():
    from app.services.knowledge_understanding.adapters.concept_index import (
        ConceptIndexUnderstandingLayer,
    )
    from app.services.knowledge_understanding.interface import (
        KnowledgeUnderstandingLayer,
    )

    assert issubclass(ConceptIndexUnderstandingLayer, KnowledgeUnderstandingLayer)


def test_builder_links_three_sources_with_explains(db_session_kul):
    db, _settings = db_session_kul
    sources = [
        _make_source(
            url="https://docs.example/getting-started",
            title="Getting Started",
            main_topic="Getting started",
            subtopics=["Installation"],
            keywords=["setup", "install"],
            canonical=True,
        ),
        _make_source(
            url="https://docs.example/api",
            title="API Reference",
            main_topic="API reference",
            subtopics=["Authentication"],
            keywords=["api", "endpoints"],
        ),
        _make_source(
            url="https://corp.example/careers",
            title="Careers",
            main_topic="Careers",
            subtopics=["Open roles"],
            keywords=["jobs"],
        ),
    ]
    for s in sources:
        db.add(s)
    db.commit()
    for s in sources:
        db.refresh(s)

    built = UnderstandingBuilder(embed_fn=_hash_embed).build(sources)
    assert built.sources_linked == 3
    assert len(built.concepts) >= 3
    explains = [e for e in built.evidence if e[2] == "explains"]
    assert len(explains) >= 3
    concept_keys = {c.concept_key for c in built.concepts}
    assert any("getting" in k or "started" in k for k in concept_keys)


def test_rebuild_persists_snapshot(db_session_kul):
    db, settings = db_session_kul
    db.add(
        _make_source(
            url="https://corp.example/privacy",
            title="Privacy",
            main_topic="Privacy policy",
            keywords=["privacy", "data"],
            canonical=True,
        )
    )
    db.commit()
    snap_id = UnderstandingRebuildService(db, settings, embed_fn=_hash_embed).rebuild()
    assert snap_id > 0

    layer = ConceptIndexUnderstandingLayer(db, enabled=True)
    concepts = layer.list_concepts()
    assert any("privacy" in c.label.lower() for c in concepts)
    matches = layer.sources_for_concept(concepts[0].concept_key)
    assert matches
