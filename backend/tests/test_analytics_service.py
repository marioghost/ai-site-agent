"""Tests for product analytics aggregations."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.answer_trace import AnswerTrace
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services.analytics_service import AnalyticsService


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_product_summary_empty(db_session):
    svc = AnalyticsService(db_session)
    data = svc.product_summary("", period_days=7)
    assert data["total_conversations"] == 0
    assert data["total_requests"] == 0


def test_popular_queries_groups(db_session):
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            AnswerTrace(
                request_id=f"req-{i}",
                original_query="loan rates",
                normalized_query="loan rates",
                answer_text="answer",
                used_context=True,
                cache_hit=i == 0,
                total_ms=100 + i * 10,
                created_at=now,
            )
        )
    db_session.commit()
    rows = AnalyticsService(db_session).popular_queries(
        fallback_answer="fallback", limit=10, period_days=30
    )
    assert len(rows) == 1
    assert rows[0]["query"] == "loan rates"
    assert rows[0]["count"] == 3


def test_intent_from_trace_json(db_session):
    steps = [
        {
            "name": "query_intent",
            "details": {"intent": "contacts_query", "matched_topic": "branches"},
        }
    ]
    db_session.add(
        AnswerTrace(
            request_id="req-intent",
            original_query="branch address",
            trace_steps_json=json.dumps(steps),
            answer_text="ok",
            used_context=True,
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    intents = AnalyticsService(db_session).intent_distribution(period_days=30)
    assert any(row["intent"] == "contacts_query" for row in intents)


def test_conversations_count(db_session):
    db_session.add(ChatSession(session_id="s1", title="Test"))
    db_session.add(
        ChatMessage(session_id="s1", role="user", content="hi")
    )
    db_session.commit()
    data = AnalyticsService(db_session).product_summary("", period_days=7)
    assert data["total_conversations"] == 1
    assert data["total_messages"] == 1
