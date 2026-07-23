"""Tests for Ollama model admin (pull/delete guards)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.settings import Settings
from app.services.ollama_model_admin_service import OllamaModelAdminError, OllamaModelAdminService
from app.services.ollama_service import OllamaError

pytestmark = pytest.mark.unit


def _settings(**kwargs) -> Settings:
    s = Settings()
    s.llm_model = kwargs.get("llm_model", "qwen2.5:3b")
    s.embedding_model = kwargs.get("embedding_model", "bge-m3")
    return s


def test_delete_blocks_active_llm_model():
    ollama = MagicMock()
    admin = OllamaModelAdminService(ollama, _settings(llm_model="qwen2.5:3b"))
    with pytest.raises(OllamaModelAdminError, match="active llm"):
        admin.delete("qwen2.5:3b")


def test_delete_blocks_active_embedding_model():
    ollama = MagicMock()
    admin = OllamaModelAdminService(ollama, _settings(embedding_model="bge-m3"))
    with pytest.raises(OllamaModelAdminError, match="active embedding"):
        admin.delete("bge-m3")


def test_delete_allows_unused_model():
    ollama = MagicMock()
    admin = OllamaModelAdminService(ollama, _settings())
    result = admin.delete("qwen2.5:7b")
    ollama.delete_model.assert_called_once_with("qwen2.5:7b")
    assert result["status"] == "success"


def test_pull_delegates_to_ollama():
    ollama = MagicMock()
    ollama.pull_model.return_value = {
        "model": "qwen2.5:3b",
        "status": "success",
        "duration_ms": 1000,
    }
    admin = OllamaModelAdminService(ollama, _settings())
    result = admin.pull("qwen2.5:3b")
    ollama.pull_model.assert_called_once_with("qwen2.5:3b")
    assert result["status"] == "success"


def test_pull_wraps_ollama_error():
    ollama = MagicMock()
    ollama.pull_model.side_effect = OllamaError("network down")
    admin = OllamaModelAdminService(ollama, _settings())
    with pytest.raises(OllamaModelAdminError, match="network down"):
        admin.pull("qwen2.5:3b")
