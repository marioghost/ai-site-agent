"""Detect local LLM runtime environment for diagnostics."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from functools import lru_cache

import httpx

from app.core.config import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


def _read_proc_mem_total_mb() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def _nvidia_visible() -> bool:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def _ollama_version(base_url: str) -> str | None:
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/version", timeout=3.0)
        if resp.status_code == 200:
            return str(resp.json().get("version") or "")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Ollama version probe failed: %s", exc)
    return None


@lru_cache(maxsize=1)
def collect_runtime_environment() -> dict:
    cfg = get_config()
    base_url = cfg.ollama_base_url
    cpu_count = os.cpu_count() or 1
    ram_mb = _read_proc_mem_total_mb()
    gpu_visible = _nvidia_visible()
    return {
        "os": platform.platform(),
        "cpu_cores": cpu_count,
        "ram_mb": ram_mb,
        "nvidia_gpu_visible": gpu_visible,
        "ollama_gpu_detectable": gpu_visible,
        "ollama_version": _ollama_version(base_url),
        "ollama_base_url": base_url,
        "ollama_num_parallel": os.environ.get("OLLAMA_NUM_PARALLEL"),
        "ollama_max_loaded_models": os.environ.get("OLLAMA_MAX_LOADED_MODELS"),
        "ollama_keep_alive_env": os.environ.get("OLLAMA_KEEP_ALIVE"),
        "runtime_mode": "gpu" if gpu_visible else "cpu",
    }


def infer_performance_bottleneck(
    *,
    load_duration_ms: int | None,
    prompt_eval_duration_ms: int | None,
    eval_duration_ms: int | None,
    time_to_first_token_ms: int | None,
    tokens_per_second: float,
    gpu_visible: bool,
) -> str | None:
    if load_duration_ms and load_duration_ms > 5000:
        return "model_cold_load"
    if prompt_eval_duration_ms and prompt_eval_duration_ms > 15000:
        return "prompt_eval_slow"
    if eval_duration_ms and eval_duration_ms > 30000 and tokens_per_second < 5:
        return "generation_slow"
    if time_to_first_token_ms and time_to_first_token_ms > 10000 and not gpu_visible:
        return "cpu_bound"
    if tokens_per_second < 2:
        return "hardware_insufficient_or_model_too_large"
    return None
