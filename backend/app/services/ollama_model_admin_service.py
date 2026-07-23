"""Admin operations for local Ollama models (pull / delete)."""
from __future__ import annotations

from app.models.settings import Settings
from app.services.model_warmup_service import ModelWarmupService
from app.services.ollama_model_utils import ollama_models_match
from app.services.ollama_service import OllamaError, OllamaService


class OllamaModelAdminError(RuntimeError):
    """Blocked or failed model admin action."""


class OllamaModelAdminService:
    def __init__(self, ollama: OllamaService, settings: Settings) -> None:
        self.ollama = ollama
        self.settings = settings

    def _protected_models(self) -> list[tuple[str, str]]:
        protected: list[tuple[str, str]] = []
        if self.settings.llm_model:
            protected.append((self.settings.llm_model, "llm"))
        if self.settings.embedding_model:
            protected.append((self.settings.embedding_model, "embedding"))
        return protected

    def model_in_use(self, model: str) -> str | None:
        for name, role in self._protected_models():
            if ollama_models_match(model, name):
                return role
        return None

    def pull(self, model: str) -> dict:
        name = (model or "").strip()
        if not name:
            raise OllamaModelAdminError("Model name is required")
        try:
            result = self.ollama.pull_model(name)
        except OllamaError as exc:
            raise OllamaModelAdminError(str(exc)) from exc
        ModelWarmupService.reset(name)
        return result

    def delete(self, model: str) -> dict:
        name = (model or "").strip()
        if not name:
            raise OllamaModelAdminError("Model name is required")
        role = self.model_in_use(name)
        if role:
            raise OllamaModelAdminError(
                f"Cannot delete {name}: it is the active {role} model. "
                "Switch to another model in Settings first."
            )
        try:
            self.ollama.delete_model(name)
        except OllamaError as exc:
            raise OllamaModelAdminError(str(exc)) from exc
        ModelWarmupService.reset(name)
        return {"model": name, "status": "success"}
