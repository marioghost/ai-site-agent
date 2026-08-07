"""Product analytics aggregations over answer traces and chat sessions."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.answer_trace import AnswerTrace
from app.models.chat_message import ChatMessage
from app.services.analytics_aggregation_service import AnalyticsAggregationService
from app.models.chat_session import ChatSession
from app.models.source import Source


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _trend(current: float, previous: float) -> dict:
    if previous == 0:
        # Avoid absurd "+∞%" spikes when the prior window was empty.
        change = None if current == 0 else 100.0
    else:
        change = round(((current - previous) / previous) * 100, 1)
        # Cap extreme relative swings so the UI stays readable under load-test spikes.
        if change > 999.0:
            change = 999.0
        elif change < -999.0:
            change = -999.0
    if change is None or abs(change) < 0.05:
        direction = "neutral"
    elif change > 0:
        direction = "up"
    else:
        direction = "down"
    return {
        "value": round(current, 4) if isinstance(current, float) else current,
        "previous_value": round(previous, 4) if isinstance(previous, float) else previous,
        "change_pct": change,
        "direction": direction,
    }


def _intent_from_row(row: AnswerTrace) -> str:
    stored = getattr(row, "query_intent", None)
    if stored and stored != "unknown":
        return stored
    try:
        steps = json.loads(row.trace_steps_json or "[]")
    except json.JSONDecodeError:
        return "unknown"
    for step in steps:
        if step.get("name") == "query_intent":
            details = step.get("details") or {}
            return str(details.get("intent") or "unknown")
    return "unknown"


def _topic_from_row(row: AnswerTrace) -> tuple[str, str]:
    key = getattr(row, "matched_topic_key", None) or ""
    label = key.replace("_", " ").title() if key else ""
    if key:
        return key, label
    try:
        steps = json.loads(row.trace_steps_json or "[]")
    except json.JSONDecodeError:
        return key or "other", label or "Other"
    for step in steps:
        if step.get("name") == "query_intent":
            details = step.get("details") or {}
            matched = details.get("matched_topic")
            if matched:
                key = str(matched)
                label = key.replace("_", " ").title()
            break
    if not key:
        key, label = "other", "Other"
    return key, label


def _chunks_from_row(row: AnswerTrace) -> list[dict]:
    try:
        data = json.loads(row.selected_chunks_json or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _sources_from_row(row: AnswerTrace) -> list[dict]:
    try:
        data = json.loads(row.sources_json or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _is_fallback(row: AnswerTrace, fallback_answer: str) -> bool:
    if fallback_answer and row.answer_text == fallback_answer:
        return True
    return not row.used_context


def _avg_score(chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    scores = [float(c.get("final_score") or 0) for c in chunks]
    return sum(scores) / len(scores) if scores else 0.0


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, fallback_answer: str) -> dict:
        agg = AnalyticsAggregationService(self.db).summary_from_aggregates()
        now = _utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = self.db.execute(
            select(func.count())
            .select_from(AnswerTrace)
            .where(AnswerTrace.created_at >= today_start)
        ).scalar_one()
        if agg:
            total = agg["total_requests"]
            cache_rate = agg["cache_hit_rate"]
            errors = agg["error_count"]
            avg_ms = agg["average_latency_ms"]
        else:
            total = self.db.execute(select(func.count()).select_from(AnswerTrace)).scalar_one()
            avg_ms = self.db.execute(
                select(func.avg(AnswerTrace.total_ms)).select_from(AnswerTrace)
            ).scalar_one()
            cache_hits = self.db.execute(
                select(func.count())
                .select_from(AnswerTrace)
                .where(AnswerTrace.cache_hit.is_(True))
            ).scalar_one()
            cache_rate = cache_hits / total if total else 0.0
            errors = self.db.execute(
                select(func.count())
                .select_from(AnswerTrace)
                .where(AnswerTrace.answer_text == fallback_answer)
            ).scalar_one() if fallback_answer else 0
            avg_ms = float(avg_ms or 0)
        p95 = self._p95_latency()
        fallbacks = self.db.execute(
            select(func.count())
            .select_from(AnswerTrace)
            .where(AnswerTrace.used_context.is_(False))
        ).scalar_one()
        fallback_rate = fallbacks / total if total else 0.0
        with_ctx = self.db.execute(
            select(func.count())
            .select_from(AnswerTrace)
            .where(AnswerTrace.used_context.is_(True))
        ).scalar_one()
        ctx_rate = with_ctx / total if total else 0.0
        return {
            "total_requests": total,
            "requests_today": today,
            "average_latency_ms": round(float(avg_ms or 0), 1),
            "p95_latency_ms": round(p95, 1),
            "cache_hit_rate": round(cache_rate, 4),
            "fallback_rate": round(fallback_rate, 4),
            "context_usage_rate": round(ctx_rate, 4),
            "error_count": errors,
        }

    def product_summary(self, fallback_answer: str, period_days: int = 7) -> dict:
        now = _utcnow()
        period_start = now - timedelta(days=period_days)
        prev_start = period_start - timedelta(days=period_days)

        # KPI counts must match the selected period (UI labels "7 days"), not all-time.
        total_conversations = self.db.execute(
            select(func.count())
            .select_from(ChatSession)
            .where(
                func.coalesce(ChatSession.last_message_at, ChatSession.updated_at, ChatSession.created_at)
                >= period_start
            )
        ).scalar_one()
        total_messages = self.db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.role.in_(("user", "assistant")),
                ChatMessage.created_at >= period_start,
            )
        ).scalar_one()
        unique_users = self.db.execute(
            select(func.count(func.distinct(AnswerTrace.user_ip)))
            .select_from(AnswerTrace)
            .where(
                AnswerTrace.user_ip.isnot(None),
                AnswerTrace.created_at >= period_start,
                AnswerTrace.created_at < now,
            )
        ).scalar_one()

        current = self._trace_metrics(period_start, now, fallback_answer)
        previous = self._trace_metrics(prev_start, period_start, fallback_answer)

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "unique_users": unique_users,
            "total_requests": current["total"],
            "successful_responses": current["successful"],
            "success_rate": round(current["success_rate"], 4),
            "context_usage_rate": round(current["context_rate"], 4),
            "cache_hit_rate": round(current["cache_rate"], 4),
            "fallback_rate": round(current["fallback_rate"], 4),
            "average_latency_ms": round(current["avg_latency"], 1),
            "trends": {
                "total_requests": _trend(current["total"], previous["total"]),
                "successful_responses": _trend(current["successful"], previous["successful"]),
                "success_rate": _trend(current["success_rate"], previous["success_rate"]),
                "context_usage_rate": _trend(current["context_rate"], previous["context_rate"]),
                "cache_hit_rate": _trend(current["cache_rate"], previous["cache_rate"]),
                "fallback_rate": _trend(current["fallback_rate"], previous["fallback_rate"]),
                "average_latency_ms": _trend(current["avg_latency"], previous["avg_latency"]),
            },
        }

    def _trace_metrics(
        self, start: datetime, end: datetime, fallback_answer: str
    ) -> dict:
        # Column projection — avoid hydrating full ORM rows for tens of thousands of traces.
        rows = self.db.execute(
            select(
                AnswerTrace.used_context,
                AnswerTrace.cache_hit,
                AnswerTrace.answer_text,
                AnswerTrace.total_ms,
            ).where(
                AnswerTrace.created_at >= start,
                AnswerTrace.created_at < end,
            )
        ).all()
        total = len(rows)
        if total == 0:
            return {
                "total": 0,
                "successful": 0,
                "success_rate": 0.0,
                "context_rate": 0.0,
                "cache_rate": 0.0,
                "fallback_rate": 0.0,
                "avg_latency": 0.0,
            }
        successful = 0
        with_ctx = 0
        cache_hits = 0
        fallbacks = 0
        latency_sum = 0
        for used_context, cache_hit, answer_text, total_ms in rows:
            is_fallback = bool(
                (fallback_answer and answer_text == fallback_answer) or (not used_context)
            )
            if is_fallback:
                fallbacks += 1
            else:
                successful += 1
            if used_context:
                with_ctx += 1
            if cache_hit:
                cache_hits += 1
            latency_sum += total_ms or 0
        return {
            "total": total,
            "successful": successful,
            "success_rate": successful / total,
            "context_rate": with_ctx / total,
            "cache_rate": cache_hits / total,
            "fallback_rate": fallbacks / total,
            "avg_latency": latency_sum / total,
        }

    def timeseries(self, hours: int = 24) -> list[dict]:
        aggregated = AnalyticsAggregationService(self.db).timeseries_from_aggregates(hours)
        if aggregated:
            return aggregated
        since = _utcnow() - timedelta(hours=hours)
        rows = self.db.execute(
            select(
                AnswerTrace.created_at,
                AnswerTrace.total_ms,
                AnswerTrace.cache_hit,
                AnswerTrace.used_context,
                AnswerTrace.answer_text,
            ).where(AnswerTrace.created_at >= since)
        ).all()
        settings_fallback = ""
        buckets: dict[str, dict] = {}
        for created_at, total_ms, cache_hit, used_context, answer_text in rows:
            if created_at is None:
                continue
            key = created_at.replace(minute=0, second=0, microsecond=0).isoformat()
            b = buckets.setdefault(
                key,
                {
                    "hour": key,
                    "count": 0,
                    "latency_sum": 0,
                    "cache_hits": 0,
                    "fallbacks": 0,
                    "with_context": 0,
                },
            )
            b["count"] += 1
            b["latency_sum"] += total_ms or 0
            if cache_hit:
                b["cache_hits"] += 1
            if not used_context:
                b["fallbacks"] += 1
            if used_context:
                b["with_context"] += 1
            _ = answer_text
        out = []
        for key in sorted(buckets):
            b = buckets[key]
            count = b["count"]
            out.append(
                {
                    "hour": b["hour"],
                    "requests": count,
                    "avg_latency_ms": round(b["latency_sum"] / count, 1) if count else 0,
                    "cache_hit_rate": round(b["cache_hits"] / count, 4) if count else 0,
                    "fallback_rate": round(b["fallbacks"] / count, 4) if count else 0,
                    "context_usage_rate": round(b["with_context"] / count, 4) if count else 0,
                }
            )
        return out

    def popular_queries(
        self,
        *,
        fallback_answer: str,
        limit: int = 20,
        search: str = "",
        period_days: int = 30,
    ) -> list[dict]:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        groups: dict[str, dict] = {}
        for row in rows:
            q = (row.original_query or "").strip()
            if not q:
                continue
            if search and search.lower() not in q.lower():
                continue
            g = groups.setdefault(
                q,
                {
                    "query": q,
                    "count": 0,
                    "latency_sum": 0,
                    "cache_hits": 0,
                    "fallback_count": 0,
                    "success_count": 0,
                },
            )
            g["count"] += 1
            g["latency_sum"] += row.total_ms or 0
            if row.cache_hit:
                g["cache_hits"] += 1
            if _is_fallback(row, fallback_answer):
                g["fallback_count"] += 1
            else:
                g["success_count"] += 1
        ranked = sorted(groups.values(), key=lambda x: x["count"], reverse=True)[:limit]
        out = []
        for g in ranked:
            count = g["count"]
            out.append(
                {
                    "query": g["query"],
                    "count": count,
                    "avg_response_ms": round(g["latency_sum"] / count, 1) if count else 0,
                    "cache_hit_rate": round(g["cache_hits"] / count, 4) if count else 0,
                    "fallback_count": g["fallback_count"],
                    "success_rate": round(g["success_count"] / count, 4) if count else 0,
                }
            )
        return out

    def problematic_queries(
        self,
        *,
        fallback_answer: str,
        timeout_ms: int = 120_000,
        limit: int = 20,
        period_days: int = 30,
    ) -> list[dict]:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        groups: dict[str, dict] = {}
        for row in rows:
            q = (row.original_query or "").strip()
            if not q:
                continue
            chunks = _chunks_from_row(row)
            score = _avg_score(chunks)
            g = groups.setdefault(
                q,
                {
                    "query": q,
                    "occurrences": 0,
                    "fallback_count": 0,
                    "timeout_count": 0,
                    "retrieval_failure_count": 0,
                    "score_sum": 0.0,
                    "score_n": 0,
                },
            )
            g["occurrences"] += 1
            if _is_fallback(row, fallback_answer):
                g["fallback_count"] += 1
            if (row.total_ms or 0) >= timeout_ms:
                g["timeout_count"] += 1
            if not row.used_context or len(chunks) == 0:
                g["retrieval_failure_count"] += 1
            if chunks:
                g["score_sum"] += score
                g["score_n"] += 1

        ranked = sorted(
            groups.values(),
            key=lambda x: (x["fallback_count"], x["retrieval_failure_count"], x["occurrences"]),
            reverse=True,
        )
        out = []
        for g in ranked[:limit]:
            if g["fallback_count"] == 0 and g["retrieval_failure_count"] == 0 and g["timeout_count"] == 0:
                continue
            out.append(
                {
                    "query": g["query"],
                    "occurrences": g["occurrences"],
                    "fallback_count": g["fallback_count"],
                    "timeout_count": g["timeout_count"],
                    "retrieval_failure_count": g["retrieval_failure_count"],
                    "avg_retrieval_score": round(g["score_sum"] / g["score_n"], 3)
                    if g["score_n"]
                    else 0.0,
                }
            )
        return out[:limit]

    def retrieval_quality(self, *, period_days: int = 7) -> dict:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        if not rows:
            return {
                "avg_retrieval_score": 0.0,
                "avg_rerank_score": 0.0,
                "avg_chunk_count": 0.0,
                "avg_context_chars": 0.0,
                "avg_prompt_chars": 0.0,
                "context_usage_rate": 0.0,
                "responses_without_context": 0,
                "avg_retrieval_ms": 0.0,
                "avg_generation_ms": 0.0,
            }
        score_sum = 0.0
        score_n = 0
        chunk_counts: list[int] = []
        context_chars: list[int] = []
        without_ctx = 0
        retrieval_ms_sum = 0
        generation_ms_sum = 0
        with_ctx = 0
        for row in rows:
            chunks = _chunks_from_row(row)
            sources = _sources_from_row(row)
            # Cache hits often omit selected_chunks_json while still using context —
            # fall back to cited sources so avg_chunk_count is not diluted toward ~0.
            evidence_n = len(chunks) if chunks else len(sources)
            chunk_counts.append(evidence_n)
            if chunks:
                score_sum += _avg_score(chunks)
                score_n += 1
                context_chars.append(
                    sum(len(str(c.get("text_preview") or "")) for c in chunks)
                )
            elif sources and row.used_context:
                score_sum += sum(float(s.get("score") or 0) for s in sources) / len(sources)
                score_n += 1
            if row.used_context:
                with_ctx += 1
            else:
                without_ctx += 1
            retrieval_ms_sum += row.retrieval_ms or 0
            generation_ms_sum += row.generation_ms or 0
        total = len(rows)
        return {
            "avg_retrieval_score": round(score_sum / score_n, 3) if score_n else 0.0,
            "avg_rerank_score": round(score_sum / score_n, 3) if score_n else 0.0,
            "avg_chunk_count": round(sum(chunk_counts) / total, 2),
            "avg_context_chars": round(sum(context_chars) / len(context_chars), 0)
            if context_chars
            else 0.0,
            "avg_prompt_chars": round(sum(context_chars) / len(context_chars) * 1.4, 0)
            if context_chars
            else 0.0,
            "context_usage_rate": round(with_ctx / total, 4),
            "responses_without_context": without_ctx,
            "avg_retrieval_ms": round(retrieval_ms_sum / total, 1),
            "avg_generation_ms": round(generation_ms_sum / total, 1),
        }

    def source_analytics(
        self, *, top_limit: int = 15, unused_limit: int = 15, period_days: int = 30
    ) -> dict:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        usage: dict[str, dict] = {}
        for row in rows:
            for src in _sources_from_row(row):
                url = str(src.get("url") or "")
                if not url:
                    continue
                title = str(src.get("title") or url)
                score = float(src.get("score") or 0)
                entry = usage.setdefault(
                    url,
                    {
                        "title": title,
                        "url": url,
                        "usage_count": 0,
                        "score_sum": 0.0,
                        "last_used_at": row.created_at,
                    },
                )
                entry["usage_count"] += 1
                entry["score_sum"] += score
                if row.created_at and (
                    entry["last_used_at"] is None or row.created_at > entry["last_used_at"]
                ):
                    entry["last_used_at"] = row.created_at

        top_pages = sorted(usage.values(), key=lambda x: x["usage_count"], reverse=True)[
            :top_limit
        ]
        top_payload = [
            {
                "title": p["title"],
                "url": p["url"],
                "usage_count": p["usage_count"],
                "avg_score": round(p["score_sum"] / p["usage_count"], 3)
                if p["usage_count"]
                else 0.0,
                "last_used_at": p["last_used_at"].isoformat() if p["last_used_at"] else None,
            }
            for p in top_pages
        ]

        indexed = list(
            self.db.execute(select(Source).where(Source.status == "indexed")).scalars()
        )
        used_urls = set(usage.keys())
        unused = [s for s in indexed if s.url not in used_urls]
        unused = sorted(
            unused,
            key=lambda s: s.indexed_at or s.created_at or _utcnow(),
            reverse=True,
        )[:unused_limit]
        unused_payload = [
            {
                "title": s.title or s.url,
                "url": s.url,
                "indexed_at": s.indexed_at.isoformat() if s.indexed_at else None,
                "document_type": s.document_type or "generic_page",
            }
            for s in unused
        ]
        return {"top_pages": top_payload, "unused_sources": unused_payload}

    def intent_distribution(self, *, period_days: int = 30) -> list[dict]:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        counts: Counter[str] = Counter()
        for row in rows:
            counts[_intent_from_row(row)] += 1
        total = sum(counts.values()) or 1
        return [
            {
                "intent": intent,
                "count": count,
                "share": round(count / total, 4),
            }
            for intent, count in counts.most_common()
        ]

    def topic_distribution(self, *, period_days: int = 30, limit: int = 12) -> list[dict]:
        since = _utcnow() - timedelta(days=period_days)
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(AnswerTrace.created_at >= since)
            ).scalars()
        )
        counts: Counter[str] = Counter()
        labels: dict[str, str] = {}
        for row in rows:
            key, label = _topic_from_row(row)
            counts[key] += 1
            labels[key] = label
        total = sum(counts.values()) or 1
        return [
            {
                "topic_key": key,
                "topic_label": labels.get(key, key),
                "count": count,
                "share": round(count / total, 4),
            }
            for key, count in counts.most_common(limit)
        ]

    def insights_and_recommendations(
        self,
        *,
        fallback_answer: str,
        period_days: int = 7,
    ) -> dict:
        summary = self.product_summary(fallback_answer, period_days=period_days)
        topics = self.topic_distribution(period_days=period_days, limit=5)
        intents = self.intent_distribution(period_days=period_days)
        sources = self.source_analytics(
            top_limit=20, unused_limit=50, period_days=period_days
        )
        retrieval = self.retrieval_quality(period_days=period_days)
        timeseries = self.timeseries(hours=period_days * 24)

        insights: list[dict] = []
        recommendations: list[dict] = []

        if topics:
            top = topics[0]
            insights.append(
                {
                    "id": "top_topic",
                    "severity": "info",
                    "message_key": "analytics.insight.top_topic",
                    "params": {"topic": top["topic_label"], "share": round(top["share"] * 100, 1)},
                }
            )

        high_fallback_topics = []
        rows = list(
            self.db.execute(
                select(AnswerTrace).where(
                    AnswerTrace.created_at >= _utcnow() - timedelta(days=period_days)
                )
            ).scalars()
        )
        topic_fallback: Counter[str] = Counter()
        topic_total: Counter[str] = Counter()
        for row in rows:
            key, label = _topic_from_row(row)
            topic_total[key] += 1
            if _is_fallback(row, fallback_answer):
                topic_fallback[key] += 1
        for key, total in topic_total.items():
            if total >= 3:
                rate = topic_fallback[key] / total
                if rate >= 0.35:
                    high_fallback_topics.append((key, rate))
        high_fallback_topics.sort(key=lambda x: x[1], reverse=True)
        if high_fallback_topics:
            key, rate = high_fallback_topics[0]
            label = key.replace("_", " ").title()
            insights.append(
                {
                    "id": "high_fallback_topic",
                    "severity": "warning",
                    "message_key": "analytics.insight.high_fallback_topic",
                    "params": {"topic": label, "rate": round(rate * 100, 1)},
                }
            )
            recommendations.append(
                {
                    "id": f"improve_{key}",
                    "stars": 5,
                    "message_key": "analytics.rec.improve_topic_docs",
                    "params": {"topic": label},
                }
            )

        if sources["top_pages"]:
            top_n = min(15, len(sources["top_pages"]))
            total_usage = sum(p["usage_count"] for p in sources["top_pages"])
            top_usage = sum(p["usage_count"] for p in sources["top_pages"][:top_n])
            if total_usage > 0:
                pct = round(top_usage / total_usage * 100)
                insights.append(
                    {
                        "id": "source_concentration",
                        "severity": "info",
                        "message_key": "analytics.insight.source_concentration",
                        "params": {"pages": top_n, "pct": pct},
                    }
                )

        if len(timeseries) >= 2:
            recent = timeseries[-1]["cache_hit_rate"]
            prev = timeseries[-2]["cache_hit_rate"]
            if prev > 0 and recent < prev * 0.88:
                drop = round((prev - recent) / prev * 100, 1)
                insights.append(
                    {
                        "id": "cache_drop",
                        "severity": "warning",
                        "message_key": "analytics.insight.cache_drop",
                        "params": {"pct": drop},
                    }
                )
                recommendations.append(
                    {
                        "id": "cache_ttl",
                        "stars": 3,
                        "message_key": "analytics.rec.increase_cache_ttl",
                        "params": {},
                    }
                )

        latency_trend = summary["trends"].get("average_latency_ms", {})
        if latency_trend.get("direction") == "up" and latency_trend.get("change_pct"):
            insights.append(
                {
                    "id": "latency_up",
                    "severity": "warning",
                    "message_key": "analytics.insight.latency_up",
                    "params": {"pct": abs(latency_trend["change_pct"])},
                }
            )

        unused_count = len(sources["unused_sources"])
        if unused_count >= 5:
            recommendations.append(
                {
                    "id": "review_unused",
                    "stars": 4,
                    "message_key": "analytics.rec.review_unused_sources",
                    "params": {"count": unused_count},
                }
            )

        if retrieval["context_usage_rate"] < 0.55 and summary["total_requests"] >= 10:
            recommendations.append(
                {
                    "id": "rebuild_embeddings",
                    "stars": 4,
                    "message_key": "analytics.rec.rebuild_embeddings",
                    "params": {},
                }
            )

        if retrieval["responses_without_context"] >= 5:
            recommendations.append(
                {
                    "id": "reindex_faq",
                    "stars": 4,
                    "message_key": "analytics.rec.reindex_faq",
                    "params": {},
                }
            )

        unknown_share = next((i["share"] for i in intents if i["intent"] == "unknown"), 0)
        if unknown_share > 0.25:
            recommendations.append(
                {
                    "id": "expand_knowledge_profile",
                    "stars": 5,
                    "message_key": "analytics.rec.expand_knowledge_profile",
                    "params": {"pct": round(unknown_share * 100, 1)},
                }
            )

        return {"insights": insights[:6], "recommendations": recommendations[:6]}

    def top_unanswered(self, fallback_answer: str, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            select(AnswerTrace.original_query, func.count())
            .where(AnswerTrace.used_context.is_(False))
            .group_by(AnswerTrace.original_query)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        return [{"query": q, "count": c} for q, c in rows]

    def slow_queries(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            select(AnswerTrace).order_by(AnswerTrace.total_ms.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "request_id": r.request_id,
                "query": r.original_query,
                "total_ms": r.total_ms,
                "cache_hit": r.cache_hit,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _p95_latency(self) -> float:
        rows = self.db.execute(
            select(AnswerTrace.total_ms).order_by(AnswerTrace.total_ms.desc()).limit(500)
        ).all()
        if not rows:
            return 0.0
        vals = sorted(r[0] or 0 for r in rows)
        idx = max(0, int(len(vals) * 0.95) - 1)
        return float(vals[idx])
