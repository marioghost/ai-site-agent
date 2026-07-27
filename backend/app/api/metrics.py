"""Operational metrics API — read-only gauges for monitoring (RFC-100 Step 025)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.operational_metrics import OperationalMetricsResponse
from app.services.operational_metrics_service import OperationalMetricsService

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics", response_class=PlainTextResponse)
def prometheus_metrics(db: Session = Depends(get_db)) -> PlainTextResponse:
    """Prometheus text exposition of Knowledge OS operational gauges."""
    body = OperationalMetricsService(db).render_prometheus()
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/api/metrics/operational", response_model=OperationalMetricsResponse)
def operational_metrics_json(db: Session = Depends(get_db)) -> OperationalMetricsResponse:
    """JSON snapshot of operational gauges (operators / integration tests)."""
    gauges = OperationalMetricsService(db).collect_gauges()
    return OperationalMetricsResponse(
        memory_version=gauges.memory_version,
        knowledge_version=gauges.knowledge_version,
        open_tensions=gauges.open_tensions,
        support_deficit_tensions=gauges.support_deficit_tensions,
        conflict_tensions=gauges.conflict_tensions,
        tension_claim_scan_limit=gauges.tension_claim_scan_limit,
    )
