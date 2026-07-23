"""Keep local Ollama models warm across requests."""
from __future__ import annotations

import threading

from app.core.logging import get_logger
from app.services.ollama_service import OllamaError, OllamaService

logger = get_logger(__name__)

_lock = threading.Lock()
_warmed: dict[str, bool] = {}
_last_warmup_ms: dict[str, int] = {}
_status: dict[str, str] = {}
_last_error: dict[str, str] = {}


class ModelWarmupService:
    @staticmethod
    def is_warm(model: str) -> bool:
        return bool(_warmed.get(model))

    @staticmethod
    def get_status(model: str) -> str:
        with _lock:
            if model in _status:
                return _status[model]
            return "warm" if _warmed.get(model) else "cold"

    @staticmethod
    def warmup(
        ollama: OllamaService,
        model: str,
        *,
        keep_alive: str = "30m",
        enabled: bool = True,
    ) -> bool:
        if not enabled or not model:
            return False
        with _lock:
            if _warmed.get(model):
                _status[model] = "warm"
                return True
            _status[model] = "warming"
            _last_error.pop(model, None)
        try:
            from time import perf_counter

            t0 = perf_counter()
            ollama.chat(
                model=model,
                system_prompt="You are a helpful assistant.",
                user_prompt="OK",
                temperature=0.0,
                max_tokens=1,
                num_ctx=512,
                keep_alive=keep_alive,
                timeout=ollama.timeout,
            )
            ms = int((perf_counter() - t0) * 1000)
            with _lock:
                _warmed[model] = True
                _last_warmup_ms[model] = ms
                _status[model] = "warm"
            logger.info("Model warmup complete: %s (%dms)", model, ms)
            return True
        except OllamaError as exc:
            with _lock:
                _status[model] = "failed"
                _last_error[model] = str(exc)
            logger.warning("Model warmup failed for %s: %s", model, exc)
            return False

    @staticmethod
    def status(model: str) -> dict:
        return {
            "model": model,
            "warm": ModelWarmupService.is_warm(model),
            "status": ModelWarmupService.get_status(model),
            "last_warmup_ms": _last_warmup_ms.get(model),
            "error": _last_error.get(model),
        }

    @staticmethod
    def reset(model: str) -> None:
        """Clear warmup state so the next warmup attempt can retry."""
        with _lock:
            _warmed.pop(model, None)
            _status.pop(model, None)
            _last_warmup_ms.pop(model, None)
            _last_error.pop(model, None)
