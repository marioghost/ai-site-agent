"""Pre-aggregated hourly analytics for fast dashboard reads."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsHourly(Base):
    __tablename__ = "analytics_hourly"

    __table_args__ = (Index("ix_analytics_hourly_hour_start", "hour_start", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hour_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0)
    intent_informational: Mapped[int] = mapped_column(Integer, default=0)
    intent_navigational: Mapped[int] = mapped_column(Integer, default=0)
    intent_transactional: Mapped[int] = mapped_column(Integer, default=0)
    intent_other: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
