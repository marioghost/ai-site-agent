"""Tests for caching helpers, reranking, source formatting and normalization."""
from __future__ import annotations

from app.services.answer_polish_service import AnswerPolishService
from app.services.qdrant_service import SearchHit
from app.services.query_normalization_service import QueryNormalizationService
from app.services.rerank_service import RerankService
from app.services.retrieval_cache_service import RetrievalCacheService
from app.services.source_formatting_service import SourceFormattingService


def _hit(score, *, text="content", title="Page", url="https://example.com"):
    return SearchHit(
        score=score,
        source_id=1,
        chunk_index=0,
        title=title,
        url=url,
        source_type="page",
        text=text,
    )


def test_normalize_collapses_and_strips():
    assert QueryNormalizationService.normalize("  Яка   КОМІСІЯ? ") == "яка комісія"
    assert QueryNormalizationService.normalize("") == ""


def test_retrieval_cache_key_is_deterministic_and_version_sensitive():
    from app.models.settings import Settings
    from app.services.cache_namespace_service import build_retrieval_namespace

    ns1 = build_retrieval_namespace(Settings(knowledge_version=1))
    ns2 = build_retrieval_namespace(Settings(knowledge_version=2))
    base = dict(
        normalized_query="яка комісія",
        top_k=5,
        similarity_threshold=0.55,
        qdrant_collection="site",
        rerank_enabled=True,
    )
    k1 = RetrievalCacheService.make_key(namespace=ns1, **base)
    k2 = RetrievalCacheService.make_key(namespace=ns1, **base)
    k3 = RetrievalCacheService.make_key(namespace=ns2, **base)
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64


def test_rerank_boosts_keyword_overlap_when_scores_equal():
    relevant = _hit(0.8, text="комісія за відкриття рахунку складає 100 грн")
    unrelated = _hit(0.8, text="графік роботи відділень")
    ordered = RerankService.rerank("яка комісія за рахунок", [unrelated, relevant])
    assert ordered[0] is relevant


def test_source_formatting_dedupes_sorts_and_limits():
    hits = [
        _hit(0.5, url="https://a.com"),
        _hit(0.9, url="https://a.com"),  # same URL, higher score wins
        _hit(0.7, url="https://b.com"),
        _hit(0.6, url=""),  # empty URL dropped
    ]
    formatted = SourceFormattingService.format(hits, limit=5)
    urls = [s.url for s in formatted]
    assert urls == ["https://a.com", "https://b.com"]
    assert formatted[0].score == 0.9


def test_polish_skips_short_only_in_fast_mode():
    assert AnswerPolishService.should_skip_short("коротка", fast_mode=True) is True
    assert AnswerPolishService.should_skip_short("коротка", fast_mode=False) is False
    long_answer = "а" * 300
    assert AnswerPolishService.should_skip_short(long_answer, fast_mode=True) is False
