"""Performance helpers for Source Intelligence (skip, hashes, stats)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.models.settings import Settings
from app.models.source import Source
from app.services.settings_flags import setting_bool
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z]{3,}")


def detect_source_language(*parts: str) -> str:
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return "unknown"
    cyr = len(_CYRILLIC_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    if cyr > lat and cyr >= 8:
        return "uk"
    if lat > cyr and lat >= 8:
        return "en"
    if cyr and lat:
        return "mixed"
    return "unknown"


def compute_llm_prompt_hash() -> str:
    from app.services.source_intelligence_llm_service import _SYSTEM_PROMPT

    return hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:32]


def compute_profile_settings_hash(settings: Settings) -> str:
    payload = {
        "enable_llm_source_intelligence": bool(
            getattr(settings, "enable_llm_source_intelligence", True)
        ),
        "llm_model": settings.llm_model or "",
        "source_intelligence_importance_threshold": int(
            getattr(settings, "source_intelligence_importance_threshold", 70) or 70
        ),
        "profile_version": SOURCE_INTELLIGENCE_VERSION,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_llm_cache_key(
    *,
    content_hash: str,
    llm_model: str,
    prompt_hash: str,
    settings_hash: str,
    language: str,
) -> str:
    parts = "|".join(
        [
            content_hash or "",
            SOURCE_INTELLIGENCE_VERSION,
            llm_model or "",
            prompt_hash or "",
            settings_hash or "",
            language or "unknown",
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def llm_enabled_for_settings(settings: Settings) -> bool:
    return setting_bool(settings, "enable_llm_source_intelligence", default=True)


def should_skip_source(
    source: Source,
    settings: Settings,
    *,
    force_reprocess: bool,
    llm_enabled: bool | None = None,
) -> bool:
    """Return True when stored profile is still valid for current content/settings."""
    if force_reprocess:
        return False
    if source.needs_intelligence:
        return False
    if (source.profile_version or "") != SOURCE_INTELLIGENCE_VERSION:
        return False
    content_hash = source.content_hash or ""
    if not content_hash:
        return False
    if (getattr(source, "intelligence_content_hash", None) or "") != content_hash:
        return False
    if (getattr(source, "intelligence_settings_hash", None) or "") != compute_profile_settings_hash(
        settings
    ):
        return False
    llm_on = llm_enabled if llm_enabled is not None else llm_enabled_for_settings(settings)
    if llm_on:
        if (getattr(source, "intelligence_llm_model", None) or "") != (settings.llm_model or ""):
            return False
        if (getattr(source, "intelligence_prompt_version", None) or "") != compute_llm_prompt_hash():
            return False
    return True


@dataclass
class IntelligenceRunStats:
    selected_sources: int = 0
    processed_sources: int = 0
    updated_sources: int = 0
    skipped_unchanged: int = 0
    llm_cache_hits: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    db_batches: int = 0
    progress_flushes: int = 0
    worker_count: int = 1
    batch_size: int = 50
    page_size: int = 100
    force_reprocess: bool = False
    stage_ms: dict[str, list[float]] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    def record_ms(self, stage: str, ms: float) -> None:
        self.stage_ms.setdefault(stage, []).append(ms)

    def avg_ms(self, stage: str) -> float:
        vals = self.stage_ms.get(stage) or []
        return sum(vals) / len(vals) if vals else 0.0

    def p95_ms(self, stage: str) -> float:
        vals = sorted(self.stage_ms.get(stage) or [])
        if not vals:
            return 0.0
        idx = max(0, int(len(vals) * 0.95) - 1)
        return vals[idx]

    def avg_per_source_ms(self) -> float:
        total = sum(sum(v) for v in self.stage_ms.values())
        n = max(self.processed_sources, 1)
        return total / n

    def estimated_remaining_seconds(self) -> int | None:
        remaining = max(0, self.selected_sources - self.processed_sources)
        if remaining <= 0:
            return 0
        avg = self.avg_per_source_ms()
        if avg <= 0:
            return None
        return int((remaining * avg) / 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_sources": self.selected_sources,
            "processed_sources": self.processed_sources,
            "updated_sources": self.updated_sources,
            "skipped_unchanged": self.skipped_unchanged,
            "llm_cache_hits": self.llm_cache_hits,
            "llm_calls": self.llm_calls,
            "llm_failures": self.llm_failures,
            "db_batches": self.db_batches,
            "progress_flushes": self.progress_flushes,
            "worker_count": self.worker_count,
            "batch_size": self.batch_size,
            "page_size": self.page_size,
            "force_reprocess": self.force_reprocess,
            "avg_ms_per_source": round(self.avg_per_source_ms(), 2),
            "avg_llm_ms": round(self.avg_ms("llm_ms"), 2),
            "avg_rules_ms": round(self.avg_ms("rules_ms"), 2),
            "estimated_remaining_seconds": self.estimated_remaining_seconds(),
            "stage_summary": {
                k: {
                    "avg": round(self.avg_ms(k), 2),
                    "p95": round(self.p95_ms(k), 2),
                    "max": round(max(v), 2) if v else 0,
                    "count": len(v),
                }
                for k, v in self.stage_ms.items()
            },
        }
