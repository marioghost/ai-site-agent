"""Release/build metadata for operators and smoke tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_config
from app.core.database import current_db_revision
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService

# RFC-100 release label — bump when acceptance report closes a release.
APP_RELEASE = "0.3"


def _project_root() -> Path:
    # backend/app/services -> repo root
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

        env_flags = {
            "KNOWLEDGE_OS_EXECUTIVE_ENABLED": self._config.knowledge_os_executive_enabled,
            "REASONING_SERVICE_ENABLED": self._config.reasoning_service_enabled,
            "EVIDENCE_ASSEMBLY_ENABLED": self._config.evidence_assembly_enabled,
        }
        settings_flags = {
            "enable_semantic_diagnostics_v2": bool(
                getattr(settings, "enable_semantic_diagnostics_v2", False)
            ),
            "cache_namespace_v2_enabled": bool(
                getattr(settings, "cache_namespace_v2_enabled", False)
            ),
            "memory_shadow_write_enabled": bool(
                getattr(settings, "memory_shadow_write_enabled", False)
            ),
        }

        return {
            "app_version": file_info.get("release") or APP_RELEASE,
            "release": file_info.get("release") or APP_RELEASE,
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
        }
