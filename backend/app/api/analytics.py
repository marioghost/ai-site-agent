"""Analytics API — product insights for administrators."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated
from app.core.concurrency import concurrency
from app.core.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.schemas.analytics import (
    AnalyticsInsight,
    AnalyticsRecommendation,
    AnalyticsSummary,
    IntentDistributionRow,
    PerformanceStatus,
    PopularQueryRow,
    ProblematicQueryRow,
    ProductAnalyticsSummary,
    RetrievalQualityMetrics,
    SlowQuery,
    SourceAnalyticsPayload,
    TimeseriesPoint,
    TopicDistributionRow,
    UnansweredQuery,
)
from app.services.analytics_service import AnalyticsService
from app.services.health_cache import health_cache

router = APIRouter(tags=["analytics"])


def _settings(db: Session):
    return SettingsRepository(db).get_or_create()


@router.get("/api/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> AnalyticsSummary:
    settings = _settings(db)
    data = AnalyticsService(db).summary(settings.fallback_answer or "")
    return AnalyticsSummary(**data)


@router.get("/api/analytics/product-summary", response_model=ProductAnalyticsSummary)
def product_analytics_summary(
    period_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> ProductAnalyticsSummary:
    settings = _settings(db)
    data = AnalyticsService(db).product_summary(
        settings.fallback_answer or "", period_days=period_days
    )
    return ProductAnalyticsSummary(**data)


@router.get("/api/analytics/timeseries", response_model=list[TimeseriesPoint])
def analytics_timeseries(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[TimeseriesPoint]:
    return [
        TimeseriesPoint(**p)
        for p in AnalyticsService(db).timeseries(hours=hours)
    ]


@router.get("/api/analytics/popular-queries", response_model=list[PopularQueryRow])
def popular_queries(
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[PopularQueryRow]:
    settings = _settings(db)
    return [
        PopularQueryRow(**row)
        for row in AnalyticsService(db).popular_queries(
            fallback_answer=settings.fallback_answer or "",
            limit=limit,
            search=search.strip(),
            period_days=period_days,
        )
    ]


@router.get("/api/analytics/problematic-queries", response_model=list[ProblematicQueryRow])
def problematic_queries(
    limit: int = Query(20, ge=1, le=100),
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[ProblematicQueryRow]:
    settings = _settings(db)
    timeout_ms = (settings.chat_total_timeout_seconds or 120) * 1000
    return [
        ProblematicQueryRow(**row)
        for row in AnalyticsService(db).problematic_queries(
            fallback_answer=settings.fallback_answer or "",
            timeout_ms=timeout_ms,
            limit=limit,
            period_days=period_days,
        )
    ]


@router.get("/api/analytics/retrieval-quality", response_model=RetrievalQualityMetrics)
def retrieval_quality(
    period_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> RetrievalQualityMetrics:
    data = AnalyticsService(db).retrieval_quality(period_days=period_days)
    return RetrievalQualityMetrics(**data)


@router.get("/api/analytics/sources", response_model=SourceAnalyticsPayload)
def source_analytics(
    top_limit: int = Query(15, ge=1, le=50),
    unused_limit: int = Query(15, ge=1, le=100),
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> SourceAnalyticsPayload:
    data = AnalyticsService(db).source_analytics(
        top_limit=top_limit, unused_limit=unused_limit, period_days=period_days
    )
    return SourceAnalyticsPayload(**data)


@router.get("/api/analytics/intents", response_model=list[IntentDistributionRow])
def intent_distribution(
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[IntentDistributionRow]:
    return [
        IntentDistributionRow(**row)
        for row in AnalyticsService(db).intent_distribution(period_days=period_days)
    ]


@router.get("/api/analytics/topics", response_model=list[TopicDistributionRow])
def topic_distribution(
    period_days: int = Query(30, ge=1, le=365),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[TopicDistributionRow]:
    return [
        TopicDistributionRow(**row)
        for row in AnalyticsService(db).topic_distribution(
            period_days=period_days, limit=limit
        )
    ]


@router.get("/api/analytics/insights")
def analytics_insights(
    period_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> dict:
    settings = _settings(db)
    data = AnalyticsService(db).insights_and_recommendations(
        fallback_answer=settings.fallback_answer or "",
        period_days=period_days,
    )
    return {
        "insights": [AnalyticsInsight(**i) for i in data["insights"]],
        "recommendations": [AnalyticsRecommendation(**r) for r in data["recommendations"]],
    }


@router.get("/api/analytics/top-unanswered", response_model=list[UnansweredQuery])
def top_unanswered(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[UnansweredQuery]:
    settings = _settings(db)
    return [
        UnansweredQuery(**q)
        for q in AnalyticsService(db).top_unanswered(
            settings.fallback_answer or "", limit=limit
        )
    ]


@router.get("/api/analytics/slow-queries", response_model=list[SlowQuery])
def slow_queries(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> list[SlowQuery]:
    return [
        SlowQuery(**q) for q in AnalyticsService(db).slow_queries(limit=limit)
    ]


@router.get("/api/system/performance", response_model=PerformanceStatus)
def system_performance(
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> PerformanceStatus:
    settings = _settings(db)
    avg, p95 = concurrency.metrics.latency_stats()
    ollama_ok, _ = health_cache.ollama()
    qdrant_ok, _ = health_cache.qdrant(settings.qdrant_collection)
    return PerformanceStatus(
        active_requests=concurrency.metrics.active_chat,
        queued_requests=concurrency.metrics.queued_chat,
        max_concurrent_llm_requests=settings.max_concurrent_llm_requests,
        average_latency_ms=round(avg, 1),
        p95_latency_ms=round(p95, 1),
        cache_hit_rate=round(concurrency.metrics.cache_hit_rate(), 4),
        ollama_status="ok" if ollama_ok else "error",
        qdrant_status="ok" if qdrant_ok else "error",
    )
