"""RFC-100 Step 005 — golden query dataset schema validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "queries.json"

REQUIRED_QUERY_FIELDS = {
    "id",
    "category",
    "query",
    "expected_intent",
    "required_response_fields",
    "required_diagnostics_keys",
    "forbidden_behaviors",
}

REQUIRED_CATEGORIES = {
    "organization_overview",
    "list_enumeration",
    "specific_fact",
    "contact_support",
    "pricing_rates",
    "process_how_to",
    "policy_legal",
    "comparison",
    "negative_absent",
    "ambiguity_clarification",
}

SMOKE_QUERY_COUNT = 30
MIN_QUERIES_PER_CATEGORY = 3

KNOWN_FORBIDDEN_BEHAVIORS = {
    "empty_answer",
    "empty_sources_when_used_context_true",
    "duplicate_assistant_answer",
    "sources_with_empty_url",
    "source_off_fixture_domain",
    "invented_enumeration_without_evidence",
}

# Industry PRESET ids must not configure the golden fixture_profile field.
# Non-golden unit tests may still use these PRESETS freely.
INDUSTRY_FIXTURE_PROFILE_IDS = {
    "bank_financial",
    "ecommerce",
    "saas",
    "documentation_portal",
    "government",
    "university",
}


@pytest.fixture()
def golden_data() -> dict:
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.unit
def test_golden_queries_file_exists_and_loads():
    assert GOLDEN_PATH.is_file()
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data["suite"] == "smoke"
    assert data["fixture_profile"] == "generic_corporate"
    assert data["fixture_profile"] not in INDUSTRY_FIXTURE_PROFILE_IDS


@pytest.mark.unit
def test_golden_fixture_profile_is_not_industry_preset(golden_data):
    profile = golden_data["fixture_profile"]
    assert profile == "generic_corporate"
    assert profile not in INDUSTRY_FIXTURE_PROFILE_IDS


@pytest.mark.unit
def test_golden_smoke_has_thirty_queries(golden_data):
    queries = golden_data["queries"]
    assert len(queries) == SMOKE_QUERY_COUNT
    ids = [q["id"] for q in queries]
    assert len(ids) == len(set(ids)), "duplicate query ids"


@pytest.mark.unit
def test_golden_each_category_has_minimum_coverage(golden_data):
    from collections import Counter

    counts = Counter(q["category"] for q in golden_data["queries"])
    for category in REQUIRED_CATEGORIES:
        assert counts.get(category, 0) >= MIN_QUERIES_PER_CATEGORY, (
            f"{category} has {counts.get(category, 0)} queries, "
            f"expected at least {MIN_QUERIES_PER_CATEGORY}"
        )


@pytest.mark.unit
def test_golden_covers_required_categories(golden_data):
    categories = {q["category"] for q in golden_data["queries"]}
    assert REQUIRED_CATEGORIES <= categories


@pytest.mark.unit
def test_golden_queries_have_required_fields(golden_data):
    for item in golden_data["queries"]:
        missing = REQUIRED_QUERY_FIELDS - set(item.keys())
        assert not missing, f"{item.get('id', '?')} missing {missing}"
        assert item["query"].strip()
        assert isinstance(item["required_response_fields"], list)
        assert isinstance(item["forbidden_behaviors"], list)


@pytest.mark.unit
def test_golden_forbidden_behaviors_use_known_vocabulary(golden_data):
    vocab = set(golden_data.get("forbidden_behavior_vocabulary", {}).keys())
    assert vocab == KNOWN_FORBIDDEN_BEHAVIORS
    for item in golden_data["queries"]:
        unknown = set(item["forbidden_behaviors"]) - vocab
        assert not unknown, f"{item['id']} unknown forbidden_behaviors: {unknown}"


@pytest.mark.unit
def test_golden_queries_are_generic_not_customer_specific(golden_data):
    blob = json.dumps(golden_data, ensure_ascii=False).lower()
    for forbidden in ("ukrsib", "укрсиб", "bank preset", "ukrsibbank"):
        assert forbidden not in blob


@pytest.mark.unit
def test_golden_does_not_lock_document_type_behavior(golden_data):
    for item in golden_data["queries"]:
        blob = json.dumps(item, ensure_ascii=False).lower()
        for legacy_lock in (
            "document_type",
            "about_page",
            "product_page",
            "boost",
            "doc_type",
        ):
            assert legacy_lock not in blob, f"{item['id']} locks legacy behavior"
