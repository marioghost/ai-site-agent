"""Hourly analytics aggregation for fast dashboard reads."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.analytics_hourly import AnalyticsHourly
from app.models.answer_trace import AnswerTrace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


class AnalyticsAggregationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def aggregate_hour(self, hour_start: datetime, *, fallback_answer: str = "") -> None:
        hour_end = hour_start + timedelta(hours=1)
        rows = list(
            self.db.scalars(
                select(AnswerTrace).where(
                    AnswerTrace.created_at >= hour_start,
                    AnswerTrace.created_at < hour_end,
                )
            ).all()
        )
        if not rows:
            return

        request_count = len(rows)
        avg_latency = sum(r.total_ms or 0 for r in rows) / request_count
        cache_hits = sum(1 for r in rows if r.cache_hit)
        errors = sum(1 for r in rows if (r.error_type or "").strip())
        fallbacks = sum(
            1
            for r in rows
            if not r.used_context
            or (fallback_answer and r.answer_text == fallback_answer)
        )
        intents = {
            "informational": 0,
            "navigational": 0,
            "transactional": 0,
            "other": 0,
        }
        for row in rows:
            intent = (row.query_intent or "other").lower()
            if intent in intents:
                intents[intent] += 1
            else:
                intents["other"] += 1

        stmt = insert(AnalyticsHourly).values(
            hour_start=hour_start,
            request_count=request_count,
            avg_latency_ms=round(avg_latency, 2),
            cache_hit_count=cache_hits,
            error_count=errors,
            fallback_count=fallbacks,
            intent_informational=intents["informational"],
            intent_navigational=intents["navigational"],
            intent_transactional=intents["transactional"],
            intent_other=intents["other"],
            updated_at=_utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["hour_start"],
            set_={
                "request_count": stmt.excluded.request_count,
                "avg_latency_ms": stmt.excluded.avg_latency_ms,
                "cache_hit_count": stmt.excluded.cache_hit_count,
                "error_count": stmt.excluded.error_count,
                "fallback_count": stmt.excluded.fallback_count,
                "intent_informational": stmt.excluded.intent_informational,
                "intent_navigational": stmt.excluded.intent_navigational,
                "intent_transactional": stmt.excluded.intent_transactional,
                "intent_other": stmt.excluded.intent_other,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self.db.execute(stmt)
        self.db.commit()

    def catch_up(self, *, max_hours: int = 168, fallback_answer: str = "") -> int:
        """Aggregate missing hourly buckets. Returns hours processed."""
        now = _hour_floor(_utcnow())
        earliest_row = self.db.execute(
            select(func.min(AnswerTrace.created_at))
        ).scalar_one_or_none()
        if earliest_row is None:
            return 0
        start = _hour_floor(earliest_row)
        if (now - start).total_seconds() / 3600 > max_hours:
            start = now - timedelta(hours=max_hours)

        existing = {
            r
            for r in self.db.scalars(
                select(AnalyticsHourly.hour_start).where(
                    AnalyticsHourly.hour_start >= start
                )
            ).all()
        }
        processed = 0
        cursor = start
        while cursor < now:
            if cursor not in existing:
                self.aggregate_hour(cursor, fallback_answer=fallback_answer)
                processed += 1
            cursor += timedelta(hours=1)
        return processed

    def timeseries_from_aggregates(self, hours: int) -> list[dict]:
        since = _hour_floor(_utcnow()) - timedelta(hours=max(1, hours))
        rows = list(
            self.db.scalars(
                select(AnalyticsHourly)
                .where(AnalyticsHourly.hour_start >= since)
                .order_by(AnalyticsHourly.hour_start.asc())
            ).all()
        )
        return [
            {
                "hour": r.hour_start.isoformat(),
                "requests": r.request_count,
                "avg_latency_ms": r.avg_latency_ms,
                "cache_hit_rate": (
                    r.cache_hit_count / r.request_count if r.request_count else 0.0
                ),
            }
            for r in rows
        ]

    def summary_from_aggregates(self) -> dict | None:
        total_requests = self.db.execute(
            select(func.coalesce(func.sum(AnalyticsHourly.request_count), 0))
        ).scalar_one()
        if not total_requests:
            return None
        avg_latency = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        AnalyticsHourly.avg_latency_ms * AnalyticsHourly.request_count
                    )
                    / func.nullif(func.sum(AnalyticsHourly.request_count), 0),
                    0,
                )
            )
        ).scalar_one()
        cache_hits = self.db.execute(
            select(func.coalesce(func.sum(AnalyticsHourly.cache_hit_count), 0))
        ).scalar_one()
        errors = self.db.execute(
            select(func.coalesce(func.sum(AnalyticsHourly.error_count), 0))
        ).scalar_one()
        return {
            "total_requests": int(total_requests),
            "average_latency_ms": float(avg_latency or 0),
            "cache_hit_rate": float(cache_hits) / float(total_requests),
            "error_count": int(errors),
        }
