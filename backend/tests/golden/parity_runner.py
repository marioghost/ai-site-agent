"""Golden chat parity runner — structural invariant checks (RFC-100 Step 006).

Unit tests use deterministic fixture ``RagResult`` values (no LLM).
Integration tests require ``POSTGRES_TEST_URL`` and ``GOLDEN_CHAT_LIVE=1``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.rag_service import RagResult, RagSource

GOLDEN_PATH = Path(__file__).resolve().parent / "queries.json"

_LIST_MARKERS_RE = re.compile(r"(\n\s*[-*•]\s+)|(, .{3,}){2,}")


class GoldenInvariantViolation(Exception):
    """Raised when a golden structural invariant fails."""


def load_golden_smoke() -> dict[str, Any]:
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("suite") != "smoke":
        raise ValueError("expected smoke golden suite")
    return data


def fixture_site_base(golden_data: dict[str, Any]) -> str:
    return golden_data.get("fixture_site_pattern", "https://example.com").rstrip("/")


def _fixture_source_url(golden_data: dict[str, Any], item: dict[str, Any]) -> str:
    base = fixture_site_base(golden_data)
    patterns = item.get("expected_source_patterns") or ["/about"]
    pattern = patterns[0]
    if not pattern.startswith("/") and "://" not in pattern:
        pattern = f"/{pattern}"
    if "://" in pattern:
        return pattern
    return f"{base}{pattern}"


def build_fixture_rag_result(golden_data: dict[str, Any], item: dict[str, Any]) -> RagResult:
    """Deterministic RagResult for CI — category-driven, not LLM-generated."""
    category = item["category"]
    intent = item["expected_intent"]
    expect_used = item.get("expect_used_context")
    request_id = f"golden-{item['id']}"

    if category == "negative_absent":
        return RagResult(
            answer="I could not find that information on the site.",
            sources=[],
            used_context=False,
            request_id=request_id,
            query_intent=intent,
            total_ms=50,
            retrieval_ms=20,
            generation_ms=30,
        )

    if category == "ambiguity_clarification":
        return RagResult(
            answer="Could you clarify which product or service you are asking about?",
            sources=[],
            used_context=False,
            request_id=request_id,
            query_intent=intent,
            total_ms=60,
            retrieval_ms=25,
            generation_ms=35,
        )

    url = _fixture_source_url(golden_data, item)
    used_context = True if expect_used is not False else False

    answers = {
        "organization_overview": "The organization provides professional services to business customers.",
        "list_enumeration": "We offer consulting, implementation, and support services.",
        "specific_fact": "Business hours are listed on the contact page.",
        "contact_support": "You can reach support through the contact page.",
        "pricing_rates": "Pricing information is published on the rates page.",
        "process_how_to": "The steps for this process are described in the help section.",
        "policy_legal": "Policy details are available in the legal section of the site.",
        "comparison": "A comparison of available options is provided on the solutions page.",
    }
    answer = answers.get(category, "Fixture answer grounded in site content.")

    if not used_context:
        answer = "I could not find that information on the site."
        sources: list[RagSource] = []
    else:
        title = {
            "organization_overview": "About Us",
            "list_enumeration": "Products and Services",
            "specific_fact": "Contact and Hours",
            "contact_support": "Contact Support",
            "pricing_rates": "Pricing and Rates",
            "process_how_to": "How-To Guide",
            "policy_legal": "Terms and Policies",
            "comparison": "Plan Comparison",
        }.get(category, "Fixture Page")
        sources = [
            RagSource(
                title=title,
                url=url,
                source_type="page",
                score=0.75,
            )
        ]

    return RagResult(
        answer=answer,
        sources=sources,
        used_context=used_context,
        request_id=request_id,
        query_intent=intent,
        total_ms=120,
        retrieval_ms=40,
        generation_ms=80,
        trace={"steps": [{"name": "retrieval", "status": "completed"}]},
        retrieval_debug={"selected_chunks": len(sources)},
    )


def build_chat_response(
    result: RagResult,
    *,
    session_id: str = "golden-session",
) -> dict[str, Any]:
    """Build API-shaped response dict from RagResult."""

    class _SettingsStub:
        knowledge_version = 1
        retrieval_mode = "hybrid"

    builder = ChatResponseBuilder(_SettingsStub())
    response = builder.from_rag_result(
        result,
        request_id=result.request_id,
        session_id=session_id,
    )
    return response.model_dump()


def build_diagnostics_payload(response_dict: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    """Diagnostics JSON shape when debug persistence is enabled."""

    class _SettingsStub:
        knowledge_version = 1
        retrieval_mode = "hybrid"

    builder = ChatResponseBuilder(_SettingsStub())
    from app.schemas.chat import ChatResponse

    response = ChatResponse(**response_dict)
    collector = DiagnosticsCollector(request_id=request_id, session_id=response.session_id)
    raw = collector.to_persistence_json(response)
    return json.loads(raw)


def check_forbidden_behavior(
    behavior: str,
    *,
    response: dict[str, Any],
    item: dict[str, Any],
    golden_data: dict[str, Any],
) -> None:
    answer = (response.get("answer") or "").strip()
    sources = response.get("sources") or []
    used_context = bool(response.get("used_context"))
    base = fixture_site_base(golden_data)

    if behavior == "empty_answer":
        if not answer:
            raise GoldenInvariantViolation(f"{item['id']}: empty_answer")
        return

    if behavior == "empty_sources_when_used_context_true":
        if used_context and not sources:
            raise GoldenInvariantViolation(f"{item['id']}: empty_sources_when_used_context_true")
        return

    if behavior == "duplicate_assistant_answer":
        for src in sources:
            title = (src.get("title") or "").strip()
            if title and title == answer:
                raise GoldenInvariantViolation(f"{item['id']}: duplicate_assistant_answer")
        return

    if behavior == "sources_with_empty_url":
        for src in sources:
            if not (src.get("url") or "").strip():
                raise GoldenInvariantViolation(f"{item['id']}: sources_with_empty_url")
        return

    if behavior == "source_off_fixture_domain":
        if not used_context:
            return
        host = urlparse(base).netloc
        for src in sources:
            url = src.get("url") or ""
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != host:
                raise GoldenInvariantViolation(
                    f"{item['id']}: source_off_fixture_domain url={url!r}"
                )
        return

    if behavior == "invented_enumeration_without_evidence":
        if item["category"] != "list_enumeration":
            return
        if used_context:
            return
        if _LIST_MARKERS_RE.search(answer):
            raise GoldenInvariantViolation(
                f"{item['id']}: invented_enumeration_without_evidence"
            )
        return

    raise GoldenInvariantViolation(f"unknown forbidden behavior: {behavior}")


def validate_golden_invariants(
    response: dict[str, Any],
    item: dict[str, Any],
    golden_data: dict[str, Any],
    *,
    include_diagnostics: bool = False,
) -> None:
    """Validate one golden query item against a response dict."""
    for field in item["required_response_fields"]:
        if field not in response:
            raise GoldenInvariantViolation(f"{item['id']}: missing field {field!r}")

    if include_diagnostics:
        diag = build_diagnostics_payload(response, request_id=response["request_id"])
        for key in item["required_diagnostics_keys"]:
            if key not in diag:
                raise GoldenInvariantViolation(
                    f"{item['id']}: missing diagnostics key {key!r}"
                )

    expect_used = item.get("expect_used_context")
    if expect_used is not None and response.get("used_context") != expect_used:
        raise GoldenInvariantViolation(
            f"{item['id']}: expect_used_context={expect_used} "
            f"got used_context={response.get('used_context')}"
        )

    patterns = item.get("expected_source_patterns") or []
    if patterns and response.get("used_context"):
        urls = " ".join((s.get("url") or "") for s in response.get("sources") or [])
        if not any(p in urls for p in patterns):
            raise GoldenInvariantViolation(
                f"{item['id']}: no source matched expected_source_patterns"
            )

    forbidden_patterns = item.get("forbidden_source_patterns") or []
    if forbidden_patterns:
        urls = " ".join((s.get("url") or "") for s in response.get("sources") or [])
        for pattern in forbidden_patterns:
            if pattern in urls:
                raise GoldenInvariantViolation(
                    f"{item['id']}: forbidden source pattern matched {pattern!r}"
                )

    metadata = response.get("metadata") or {}
    intent = metadata.get("query_intent")
    allowed_intents = {item["expected_intent"]} | set(
        item.get("expected_intent_alternatives") or []
    )
    if intent and intent not in allowed_intents:
        raise GoldenInvariantViolation(
            f"{item['id']}: query_intent {intent!r} not in {allowed_intents}"
        )

    for behavior in item.get("forbidden_behaviors") or []:
        check_forbidden_behavior(
            behavior, response=response, item=item, golden_data=golden_data
        )


def compare_structural_parity(
    legacy: dict[str, Any],
    executive: dict[str, Any],
    *,
    query_id: str,
) -> None:
    """Legacy and executive paths must produce structurally equivalent responses."""
    if set(legacy.keys()) != set(executive.keys()):
        raise GoldenInvariantViolation(
            f"{query_id}: response key mismatch "
            f"legacy-only={set(legacy) - set(executive)} "
            f"executive-only={set(executive) - set(legacy)}"
        )

    for key in ("used_context", "cache_hit", "cache_type", "error_type"):
        if legacy.get(key) != executive.get(key):
            raise GoldenInvariantViolation(
                f"{query_id}: parity mismatch on {key}: "
                f"legacy={legacy.get(key)!r} executive={executive.get(key)!r}"
            )

    legacy_sources = legacy.get("sources") or []
    executive_sources = executive.get("sources") or []
    if len(legacy_sources) != len(executive_sources):
        raise GoldenInvariantViolation(f"{query_id}: source count mismatch")

    legacy_urls = [s.get("url") for s in legacy_sources]
    executive_urls = [s.get("url") for s in executive_sources]
    if legacy_urls != executive_urls:
        raise GoldenInvariantViolation(f"{query_id}: source url mismatch")

    legacy_meta = legacy.get("metadata") or {}
    executive_meta = executive.get("metadata") or {}
    if legacy_meta.get("query_intent") != executive_meta.get("query_intent"):
        raise GoldenInvariantViolation(f"{query_id}: metadata.query_intent mismatch")

    legacy_timing = legacy.get("timing") or {}
    executive_timing = executive.get("timing") or {}
    for timing_key in ("total_ms", "retrieval_ms", "generation_ms", "polish_ms"):
        if timing_key in legacy_timing or timing_key in executive_timing:
            if legacy_timing.get(timing_key) != executive_timing.get(timing_key):
                raise GoldenInvariantViolation(
                    f"{query_id}: timing.{timing_key} mismatch"
                )

    # Deliberately do NOT compare answer text tokens/scores/document_type.
