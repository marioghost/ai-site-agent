"""Light lexical morphology for FTS simple (no language stemmer)."""
from __future__ import annotations

import pytest

from app.services.lexical_index_service import LexicalIndexService, lexical_term_variants

pytestmark = pytest.mark.unit


def test_ukrainian_case_ending_adds_stem_variant():
    variants = lexical_term_variants("депозитах")
    assert "депозитах" in variants
    assert "депозит" in variants


def test_match_query_includes_stem_and_drops_stopwords():
    q = LexicalIndexService.build_match_query(
        ["які", "ставки", "по", "депозитах"],
        phrase="Які ставки по депозитах?",
    )
    assert "депозит" in q
    assert "депозитах" in q
    # Function words should not dominate the OR clause.
    assert "'по'" not in q
    assert "'які'" not in q


def test_english_plural_light_stem():
    variants = lexical_term_variants("rates")
    assert "rates" in variants
    assert "rate" in variants
