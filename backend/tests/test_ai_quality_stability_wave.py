"""Release 1.0 AI quality & stability — regression coverage for production answer defects."""
from __future__ import annotations

import pytest

from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile, SourcePriorityRule
from app.services.canonical_source_service import CanonicalSourceService
from app.services.llm_mode_service import effective_generation_settings
from app.services.llm_options_service import resolve_llm_options
from app.services.llm_runtime_profiler import LlmRuntimeMetrics
from app.services.ollama_service import OllamaChatResult, _parse_chat_stats
from app.services.rag_planning.intent_taxonomy import is_overview_intent
from app.services.qdrant_service import SearchHit
from app.services.rag_service import RagResult, RagSource
from app.services.reasoning.evidence_sufficiency import assess_evidence_sufficiency
from app.services.reasoning.speech_act import select_speech_act
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder


def _src(url: str = "https://site/about", title: str = "About") -> RagSource:
    return RagSource(title=title, url=url, source_type="page", score=0.9)


def _hit(
    source_id: int,
    *,
    document_type: str,
    score: float,
    is_homepage: bool = False,
    url: str = "",
) -> SearchHit:
    return SearchHit(
        score=score,
        source_id=source_id,
        chunk_index=0,
        title=document_type,
        url=url or f"https://site/{source_id}",
        source_type="page",
        text="body",
        heading="",
        is_homepage=is_homepage,
        document_type=document_type,
        final_score=score,
    )


@pytest.mark.unit
def test_high_quality_overview_keeps_full_num_predict_budget():
    """Overview answers must not be artificially clamped to 180 tokens."""
    settings = Settings(llm_mode_profile="high_quality")
    opts = resolve_llm_options(settings, prompt_chars=2000)
    assert is_overview_intent("entity_overview")
    assert opts["num_predict"] == 512
    assert effective_generation_settings(settings)["llm_num_predict"] == 512


@pytest.mark.unit
def test_balanced_overview_keeps_profile_num_predict():
    settings = Settings(llm_mode_profile="balanced")
    opts = resolve_llm_options(settings, prompt_chars=2000)
    assert opts["num_predict"] == 240


@pytest.mark.unit
def test_parse_chat_stats_captures_done_reason():
    stats = _parse_chat_stats(
        {
            "model": "qwen2.5:3b",
            "message": {"content": "Partial"},
            "eval_count": 180,
            "done_reason": "length",
        },
        model="qwen2.5:3b",
    )
    assert stats.done_reason == "length"
    assert stats.eval_count == 180


@pytest.mark.unit
def test_metrics_flag_output_truncated_on_length_stop():
    metrics = LlmRuntimeMetrics(num_predict=180)
    metrics.apply_ollama_stats(
        OllamaChatResult(content="…використовуючи най", eval_count=180, done_reason="length"),
        generation_ms=29000,
    )
    assert metrics.output_truncated is True
    assert metrics.generation_stop_reason == "length"
    assert metrics.done_reason == "length"


@pytest.mark.unit
def test_metrics_flag_truncation_when_eval_count_hits_cap_without_reason():
    metrics = LlmRuntimeMetrics(num_predict=180)
    metrics.apply_ollama_stats(
        OllamaChatResult(content="cut mid-word", eval_count=180, done_reason=None),
        generation_ms=1000,
    )
    assert metrics.output_truncated is True
    assert metrics.generation_stop_reason == "length"


@pytest.mark.unit
def test_metrics_clean_stop_not_truncated():
    metrics = LlmRuntimeMetrics(num_predict=512)
    metrics.apply_ollama_stats(
        OllamaChatResult(content="Complete answer.", eval_count=120, done_reason="stop"),
        generation_ms=1000,
    )
    assert metrics.output_truncated is False
    assert metrics.generation_stop_reason == "stop"


@pytest.mark.unit
def test_entity_overview_with_evidence_is_sufficient_not_completeness_risk():
    result = RagResult(
        answer="Overview",
        sources=[_src(), _src("https://site/history", "History")],
        used_context=True,
        request_id="req-quality",
        query_intent="entity_overview",
        applied_knowledge_config={"answer_strategy": "overview"},
    )
    assessment = assess_evidence_sufficiency(result)
    assert assessment.sufficiency_status == "sufficient"
    assert assessment.evidence_sufficient is True
    assert assessment.completeness_risk is False
    decision = select_speech_act(assessment, information_need="entity_overview")
    assert decision.speech_act == "answer"
    assert decision.qualification_required is False


@pytest.mark.unit
def test_list_strategy_still_qualifies_for_completeness_risk():
    result = RagResult(
        answer="List",
        sources=[_src(), _src("https://site/services", "Services")],
        used_context=True,
        request_id="req-list",
        query_intent="entity_overview",
        applied_knowledge_config={"answer_strategy": "list"},
    )
    assessment = assess_evidence_sufficiency(result)
    assert assessment.completeness_risk is True
    decision = select_speech_act(assessment, information_need="entity_overview")
    assert decision.speech_act == "qualify"


@pytest.mark.unit
def test_prefer_profile_order_puts_about_before_news_and_homepage_promo():
    profile = KnowledgeProfile(
        organization_name="Bank",
        source_priority_rules=[
            SourcePriorityRule(
                query_intent="entity_overview",
                boost_document_types=["about_page", "homepage"],
                deprioritize_document_types=["news_page", "promotion_page"],
            )
        ],
    )
    # Intentional score trap: news and homepage outscore about.
    hits = [
        _hit(3, document_type="news_page", score=0.95),
        _hit(1, document_type="homepage", score=0.9, is_homepage=True),
        _hit(2, document_type="about_page", score=0.5),
    ]
    ordered = CanonicalSourceService.prefer_profile_order(
        hits, "entity_overview", profile=profile
    )
    assert [h.document_type for h in ordered] == ["about_page", "homepage", "news_page"]


@pytest.mark.unit
def test_metrics_respect_explicit_stop_even_if_eval_equals_cap():
    metrics = LlmRuntimeMetrics(num_predict=180)
    metrics.apply_ollama_stats(
        OllamaChatResult(content="Done.", eval_count=180, done_reason="stop"),
        generation_ms=1000,
    )
    assert metrics.output_truncated is False
    assert metrics.generation_stop_reason == "stop"


@pytest.mark.unit
def test_admin_system_prompt_is_sole_behavior_contract():
    settings = Settings(
        llm_mode_profile="high_quality",
        system_prompt="CUSTOM AGENT RULES: be concise and cite sources.",
    )
    system, user = CompactPromptBuilder.build(
        message="розкажи про банк",
        hits=[],
        built_context=None,
        intent="entity_overview",
        settings=settings,
        org_name="UKRSIBBANK",
    )
    assert system == "CUSTOM AGENT RULES: be concise and cite sources."
    assert "Evidence:" in user
    assert "Instruction:" in user  # overview scope instruction


@pytest.mark.unit
def test_empty_system_prompt_falls_back_to_behavior_contract():
    settings = Settings(llm_mode_profile="high_quality", system_prompt="")
    system, user = CompactPromptBuilder.build(
        message="who are you",
        hits=[],
        built_context=None,
        intent="factual",
        settings=settings,
        speech_act_guidance="QUALIFY_INCOMPLETE_EVIDENCE",
    )
    assert "AI-помічник цього вебсайту" in system
    assert "Sources" in system
    assert "Instruction" in system
    assert "QUALIFY_INCOMPLETE_EVIDENCE" in user
    assert "на основі інформації на сайті" not in system.lower()


@pytest.mark.unit
def test_finish_if_truncated_keeps_last_complete_sentence():
    from app.services.answer_completion import finish_if_truncated

    partial = (
        "UKRSIBBANK — один з найбільших банків України. "
        "Він входить до BNP Paribas Group. Банк також пропонує знижки на карт"
    )
    finished = finish_if_truncated(partial, truncated=True)
    assert finished.endswith("Group.")
    assert "знижки" not in finished
    assert finish_if_truncated(partial, truncated=False) == partial.rstrip()


@pytest.mark.unit
def test_preview_prompt_keeps_question_tail():
    from app.services.answer_completion import preview_prompt

    user = (
        "Sources:\n" + ("x" * 3000)
        + "\n\nInstruction: QUALIFY_INCOMPLETE_EVIDENCE\n\nQuestion: who?\n\nAnswer:"
    )
    preview = preview_prompt(user, 2000)
    assert "Instruction: QUALIFY_INCOMPLETE_EVIDENCE" in preview
    assert "Question: who?" in preview
    assert "Sources:" in preview


@pytest.mark.unit
def test_truncate_prompts_preserves_question_anchor():
    system = "sys"
    user = (
        "Sources:\n" + ("x" * 5000)
        + "\n\nInstruction: ANSWER\n\nQuestion: who?\n\nAnswer:"
    )
    truncated_system, truncated_user = CompactPromptBuilder.truncate_prompts(system, user, 800)
    assert truncated_system == system
    assert "\n\nQuestion: who?\n\nAnswer:" in truncated_user
    assert "Instruction:" in truncated_user
    assert len(truncated_system) + len(truncated_user) + 2 <= 800 or truncated_user.endswith(
        "Question: who?\n\nAnswer:"
    )


@pytest.mark.unit
def test_truncate_prompts_keeps_earlier_evidence_block_before_later_one():
    system = "sys"
    user = (
        "Evidence:\n"
        "Source 1:\nTitle: About\nURL: https://site/about\nEvidence excerpt:\n"
        + ("A" * 420)
        + "\n\n---\n\n"
        "Source 2:\nTitle: News\nURL: https://site/news\nEvidence excerpt:\n"
        + ("B" * 420)
        + "\n\nInstruction: ANSWER\n\nQuestion: who?\n\nAnswer:"
    )
    _, truncated_user = CompactPromptBuilder.truncate_prompts(system, user, 760)
    assert "Source 1:" in truncated_user
    assert "Question: who?" in truncated_user
    assert truncated_user.index("Source 1:") < truncated_user.index("Instruction: ANSWER")
    assert "Source 2:" not in truncated_user
    assert "BBBB" not in truncated_user


@pytest.mark.unit
def test_extract_evidence_text_returns_exact_prompt_evidence_block():
    user = (
        "Evidence:\n"
        "Source 1:\nTitle: About\nURL: https://site/about\nEvidence excerpt:\nCore text"
        "\n\nInstruction: ANSWER\n\nQuestion: who?\n\nAnswer:"
    )
    evidence = CompactPromptBuilder.extract_evidence_text(user)
    assert evidence.startswith("Source 1:")
    assert evidence.endswith("Core text")
