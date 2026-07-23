"""Tests for ollama model name matching."""
import pytest

from app.services.ollama_model_utils import ollama_model_installed, ollama_models_match

pytestmark = pytest.mark.unit


def test_model_installed_exact():
    assert ollama_model_installed("qwen2.5:3b", ["qwen2.5:3b", "bge-m3"])


def test_model_installed_latest_tag():
    assert ollama_model_installed("bge-m3", ["bge-m3:latest"])


def test_model_not_installed():
    assert not ollama_model_installed("qwen2.5:3b", ["qwen2.5:7b"])


def test_models_match():
    assert ollama_models_match("bge-m3", "bge-m3:latest")
