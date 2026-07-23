"""Admin LLM benchmark and runtime diagnostics API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated
from app.core.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.schemas.llm import LlmBenchmarkResponse, LlmRuntimeInfoResponse
from app.services.llm_benchmark_service import LlmBenchmarkService
from app.services.llm_runtime_environment import collect_runtime_environment
from app.services.model_warmup_service import ModelWarmupService
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["llm"])


from app.services.ollama_model_utils import ollama_model_installed

@router.post("/api/llm/benchmark", response_model=LlmBenchmarkResponse)
def llm_benchmark(
    _user=Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> LlmBenchmarkResponse:
    settings = SettingsRepository(db).get_or_create()
    service = LlmBenchmarkService(OllamaService(timeout=120.0), settings)
    return LlmBenchmarkResponse(**service.run())


@router.get("/api/llm/runtime", response_model=LlmRuntimeInfoResponse)
def llm_runtime_info(
    _user=Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> LlmRuntimeInfoResponse:
    settings = SettingsRepository(db).get_or_create()
    ollama = OllamaService()
    ok, detail = ollama.health()
    env = collect_runtime_environment()
    warmup = ModelWarmupService.status(settings.llm_model)
    installed = [
        str(m.get("name") or m.get("model") or "")
        for m in ollama.list_models()
        if m.get("name") or m.get("model")
    ]
    active = settings.llm_model
    model_installed = ollama_model_installed(active, installed)
    return LlmRuntimeInfoResponse(
        ollama_reachable=ok,
        ollama_detail=detail,
        ollama_version=env.get("ollama_version"),
        active_model=active,
        model_installed=model_installed,
        installed_models=installed,
        warmup=warmup,
        environment=env,
        recommended_models=[
            {
                "name": "qwen2.5:3b",
                "quality": "good",
                "speed": "fast",
                "ukrainian": "good",
                "use": "default fast local chat",
            },
            {
                "name": "llama3.2:3b",
                "quality": "good",
                "speed": "fast",
                "ukrainian": "fair",
                "use": "low-resource CPU",
            },
            {
                "name": "gemma2:2b",
                "quality": "fair",
                "speed": "very fast",
                "ukrainian": "fair",
                "use": "smoke tests / dev",
            },
            {
                "name": "phi3:mini",
                "quality": "good",
                "speed": "fast",
                "ukrainian": "fair",
                "use": "compact English-heavy workloads",
            },
            {
                "name": "qwen2.5:7b",
                "quality": "very good",
                "speed": "slow on CPU",
                "ukrainian": "very good",
                "use": "quality mode with GPU",
            },
        ],
    )
