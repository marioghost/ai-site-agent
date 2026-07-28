"""Release/build metadata for operators and smoke tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import AppConfig, get_config
from app.core.database import current_db_revision
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService

# Last *accepted* RFC-100 release. Release 0.6 steps may exist in repo but are
# not closed — do not claim 0.6 complete.
APP_RELEASE = "0.5"

_ENV_CAPABILITIES = (
    (
        "KNOWLEDGE_OS_EXECUTIVE_ENABLED",
        "knowledge_os_executive_enabled",
        "Executive seam",
        False,
        "Route chat through ExecutiveService instead of direct RagService",
        "Release 1.0 default ON",
    ),
    (
        "REASONING_SERVICE_ENABLED",
        "reasoning_service_enabled",
        "Reasoning seam",
        False,
        "Route chat through ReasoningService (diagnostics + optional Language)",
        "Release 1.0 default ON",
    ),
    (
        "EVIDENCE_ASSEMBLY_ENABLED",
        "evidence_assembly_enabled",
        "Evidence Assembly seam",
        False,
        "Route RPS assemble stage through EvidenceAssemblyService",
        "Release 1.0 default ON",
    ),
    (
        "REASONING_SPEECH_ACTS_ENABLED",
        "reasoning_speech_acts_enabled",
        "Speech-act Language rendering",
        False,
        "Language applies clarify/refuse/qualify when Reasoning is ON",
        "Requires Reasoning ON; Step 045 must be deployed",
    ),
)

_SETTINGS_CAPABILITIES = (
    (
        "enable_semantic_diagnostics_v2",
        "Semantic diagnostics v2 stub",
        False,
        "Empty understanding_trace on chat when debug enabled",
        "Release 1.0",
    ),
    (
        "cache_namespace_v2_enabled",
        "Cache namespace v2",
        False,
        "Include memory_version in retrieval/answer cache namespace",
        "Staging validation",
    ),
    (
        "memory_shadow_write_enabled",
        "Memory shadow write",
        False,
        "Persist SI claim proposals to Epistemic Memory (shadow; not used by chat)",
        "Default OFF until 0.7 assist",
    ),
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_build_file() -> dict[str, str]:
    path = _project_root() / ".build-info.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


class BuildInfoService:
    """Collect deploy/build metadata for GET /api/build."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._config = get_config()

    def collect(self) -> dict:
        settings = SettingsRepository(self._db).get_or_create()
        file_info = _load_build_file()
        revision = current_db_revision()
        fields = getattr(AppConfig, "model_fields", {}) or {}

        env_flags: dict[str, bool] = {}
        deployed: dict[str, dict] = {}

        for flag_name, attr, friendly, default, effect, rollout in _ENV_CAPABILITIES:
            supported = attr in fields
            value: bool | None = None
            if supported:
                raw = getattr(self._config, attr, False)
                value = raw if isinstance(raw, bool) else False
                env_flags[flag_name] = value
            deployed[flag_name] = {
                "supported": supported,
                "value": value,
                "surface": "env",
                "friendly_name": friendly,
                "default": default,
                "effect": effect,
                "rollout": rollout,
            }

        settings_flags: dict[str, bool] = {}
        for flag_name, friendly, default, effect, rollout in _SETTINGS_CAPABILITIES:
            value = bool(getattr(settings, flag_name, False))
            settings_flags[flag_name] = value
            deployed[flag_name] = {
                "supported": True,
                "value": value,
                "surface": "settings",
                "friendly_name": friendly,
                "default": default,
                "effect": effect,
                "rollout": rollout,
            }

        release = file_info.get("release") or APP_RELEASE
        return {
            "app_version": release,
            "release": release,
            "git_commit": file_info.get("git_commit")
            or os.getenv("GIT_COMMIT")
            or None,
            "git_commit_short": file_info.get("git_commit_short") or None,
            "build_time": file_info.get("build_time") or os.getenv("BUILD_TIME") or None,
            "alembic_head": revision,
            "memory_version": MemoryVersionService(self._db).get(),
            "knowledge_version": KnowledgeVersionService(self._db).get(),
            "feature_flags": {**env_flags, **settings_flags},
            "env_flags": env_flags,
            "settings_flags": settings_flags,
            "release_status": {
                "accepted": "0.5",
                "in_progress": "0.6",
                "closed_0_6": False,
                "note": (
                    "Release 0.5 accepted. Release 0.6 steps may exist in the "
                    "repository; release is not closed. Deployed capability set "
                    "is reported per process — Step 045 may be missing on older deploys."
                ),
            },
            "deployed_capabilities": deployed,
        }
