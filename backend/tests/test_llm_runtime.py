"""Tests for Ollama runtime profiler and options."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.settings import Settings
from app.services.llm_call_tracker import LlmCallTracker
from app.services.llm_mode_service import effective_generation_settings, get_mode_profile
from app.services.llm_options_service import resolve_llm_options
from app.services.llm_runtime_profiler import LlmRuntimeMetrics
from app.services.ollama_service import OllamaChatResult, OllamaService, OllamaStreamChunk, _parse_chat_stats


@pytest.mark.unit
def test_fast_profile_defaults():
    settings = Settings()
    eff = effective_generation_settings(settings)
    profile = get_mode_profile(settings)
    assert profile.key == "fast"
    assert eff["llm_num_predict"] == 160
    assert eff["max_total_context_chars"] == 1800
    assert eff["generation_timeout_seconds"] == 45
    assert eff["llm_retry_max_attempts"] == 0


@pytest.mark.unit
def test_resolve_llm_options_passes_keep_alive_and_sampling():
    opts = resolve_llm_options(Settings(), prompt_chars=1200)
    assert opts["keep_alive"] == "30m"
    assert opts["repeat_penalty"] == 1.05
    assert opts["num_predict"] == 160


@pytest.mark.unit
def test_parse_chat_stats_includes_prompt_eval_duration():
    stats = _parse_chat_stats(
        {
            "model": "qwen2.5:7b",
            "message": {"content": "OK"},
            "prompt_eval_count": 10,
            "eval_count": 2,
            "total_duration": 5_000_000_000,
            "eval_duration": 1_000_000_000,
            "prompt_eval_duration": 3_000_000_000,
            "load_duration": 500_000_000,
        },
        model="qwen2.5:7b",
    )
    assert stats.prompt_eval_duration_ns == 3_000_000_000
    assert stats.eval_count == 2


@pytest.mark.unit
def test_metrics_apply_ollama_stats_sets_bottleneck():
    metrics = LlmRuntimeMetrics()
    stats = OllamaChatResult(
        content="answer",
        prompt_eval_count=1200,
        eval_count=40,
        load_duration_ns=6_000_000_000,
        prompt_eval_duration_ns=20_000_000_000,
        eval_duration_ns=35_000_000_000,
    )
    metrics.apply_ollama_stats(stats, first_token_ms=25000, generation_ms=40000, gpu_visible=False)
    assert metrics.time_to_first_token_ms == 25000
    assert metrics.load_duration_ms == 6000
    assert metrics.prompt_eval_duration_ms == 20000
    assert metrics.performance_bottleneck in {
        "model_cold_load",
        "prompt_eval_slow",
        "cpu_bound",
        "generation_slow",
        "hardware_insufficient_or_model_too_large",
    }


@pytest.mark.unit
def test_llm_call_tracker_counts_reasons():
    tracker = LlmCallTracker()
    tracker.record("rag_generation")
    assert tracker.count == 1
    assert tracker.to_dict()["llm_call_reasons"] == ["rag_generation"]


@pytest.mark.unit
def test_chat_stream_parses_done_stats_without_buffering_tokens():
    payload_done = json.dumps(
        {
            "model": "m",
            "done": True,
            "message": {"content": "Hi"},
            "eval_count": 1,
            "prompt_eval_count": 5,
            "total_duration": 1_000_000,
            "eval_duration": 500_000,
            "prompt_eval_duration": 400_000,
            "load_duration": 0,
        }
    )

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield json.dumps({"message": {"content": "H"}, "done": False})
            yield payload_done

    fake_client = MagicMock()
    fake_client.stream.return_value = FakeResp()
    service = OllamaService(base_url="http://test", timeout=5)
    with patch.object(service, "_client", return_value=fake_client):
        with patch("app.services.ollama_service.concurrency.llm_slot") as slot:
            slot.return_value.__enter__.return_value = None
            slot.return_value.__exit__.return_value = None
            chunks = list(
                service.chat_stream(
                    "m",
                    system_prompt="s",
                    user_prompt="u",
                    keep_alive="30m",
                )
            )
    assert chunks[0].text == "H"
    assert chunks[-1].done is True
    assert chunks[-1].stats is not None
    assert chunks[-1].stats.eval_count == 1
