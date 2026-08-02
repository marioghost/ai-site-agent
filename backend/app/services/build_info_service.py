"""Release/build metadata for operators and smoke tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import AppConfig, get_config
from app.core.database import current_db_revision
from app.repositories.settings_repository import SettingsRepository
from app.services.feature_flags import (
    env_bool_flag_definitions,
    maintenance_observation,
    settings_flag_definitions,
)
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.memory_version_service import MemoryVersionService

# Last accepted RFC-100 release (engineering closure 2026-07-31).
APP_RELEASE = "0.9"

# Release 0.6 cognitive pipeline — code present when repo includes Steps 039–045.
RELEASE_0_6_STEPS = (
    {"step": "039", "title": "ReasoningService seam", "code": "present"},
    {"step": "040", "title": "EvidenceAssemblyService seam", "code": "present"},
    {"step": "041", "title": "Thin RPS coordination", "code": "present"},
    {"step": "042", "title": "Migration Confidence Gate", "code": "present"},
    {"step": "043", "title": "Advisory evidence sufficiency", "code": "present"},
    {"step": "044", "title": "Advisory speech-act selection", "code": "present"},
    {"step": "045", "title": "Language speech-act rendering", "code": "present"},
)

# Release 0.7 Memory integration — code present; flags default OFF; staging not validated.
RELEASE_0_7_STEPS = (
    {"step": "046", "title": "Memory region read views", "code": "present"},
    {"step": "047", "title": "Advisory Memory evidence assist", "code": "present"},
    {"step": "048", "title": "Memory canonical shadow comparator", "code": "present"},
    {"step": "049", "title": "Offline Memory Assist evaluation", "code": "present"},
    {"step": "050", "title": "Release 0.7 engineering closure", "code": "present"},
)

# Release 0.8 legacy surface cleanup — code present; staging/production not validated.
RELEASE_0_8_STEPS = (
    {"step": "052", "title": "Settings API boost field removal", "code": "present"},
    {"step": "053", "title": "Dashboard boost inputs removal", "code": "present"},
    {"step": "054", "title": "Legacy KP presets default off (410)", "code": "present"},
    {"step": "055", "title": "Legacy doc-type canonical flag", "code": "present"},
    {"step": "056", "title": "Golden generic profile CI fail-closed", "code": "present"},
    {"step": "057", "title": "Release 0.8 engineering closure", "code": "present"},
)

# Release 0.9 active maintenance — code present; execution default OFF; staging/production not validated.
RELEASE_0_9_STEPS = (
    {"step": "058", "title": "Maintenance agenda ranking", "code": "present"},
    {"step": "059", "title": "Maintenance cycle orchestration", "code": "present"},
    {"step": "060", "title": "Investigation execution (fetch)", "code": "present"},
    {"step": "061", "title": "Investigation metrics", "code": "present"},
    {"step": "062", "title": "Release 0.9 engineering closure", "code": "present"},
)

# Release 1.0 (in progress) — Step 063+
RELEASE_1_0_STEPS = (
    {
        "step": "063",
        "title": "Default knowledge_os flags ON",
        "code": "present",
    },
    {
        "step": "064",
        "title": "Remove legacy direct RagService path from chat (keep emergency env)",
        "code": "present",
    },
    {
        "step": "065",
        "title": "Remove hybrid flag registry entries",
        "code": "present",
    },
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
        maint = maintenance_observation()

        for definition in env_bool_flag_definitions():
            if definition.key == "MAINTENANCE_EXECUTION_ENABLED":
                supported = True
                value = bool(maint["execution_enabled"])
            else:
                attr = definition.config_attr or ""
                supported = attr in fields
                value = None
                if supported:
                    raw = getattr(self._config, attr, False)
                    value = raw if isinstance(raw, bool) else False
            if value is not None:
                env_flags[definition.key] = value
            deployed[definition.key] = {
                "supported": supported,
                "value": value,
                "surface": "env",
                "friendly_name": definition.friendly_name,
                "default": definition.default,
                "effect": definition.effect,
                "rollout": definition.rollout,
                "active": bool(value),
                "code_present": supported,
                "classification": definition.classification,
                "runtime_owner": definition.runtime_owner,
            }

        settings_flags: dict[str, bool] = {}
        for definition in settings_flag_definitions():
            flag_name = definition.key
            value = bool(getattr(settings, flag_name, False))
            settings_flags[flag_name] = value
            entry = {
                "supported": True,
                "value": value,
                "surface": "settings",
                "friendly_name": definition.friendly_name,
                "default": definition.default,
                "effect": definition.effect,
                "rollout": definition.rollout,
                "active": bool(value),
                "code_present": True,
                "classification": definition.classification,
                "runtime_owner": definition.runtime_owner,
            }
            if flag_name == "memory_evidence_assist_enabled":
                entry["effective"] = bool(
                    env_flags.get("REASONING_SERVICE_ENABLED", False)
                    and value
                    and settings_flags.get("cache_namespace_v2_enabled", False)
                )
                if value and not env_flags.get("REASONING_SERVICE_ENABLED", False):
                    entry["skipped_reason"] = "reasoning_disabled"
                elif value and not settings_flags.get("cache_namespace_v2_enabled", False):
                    entry["skipped_reason"] = "cache_namespace_v2_required"
            if flag_name == "memory_canonical_shadow_enabled":
                entry["effective"] = bool(
                    env_flags.get("REASONING_SERVICE_ENABLED", False)
                    and value
                    and settings_flags.get("memory_evidence_assist_enabled", False)
                    and settings_flags.get("cache_namespace_v2_enabled", False)
                )
                if value and not env_flags.get("REASONING_SERVICE_ENABLED", False):
                    entry["skipped_reason"] = "reasoning_disabled"
                elif value and not settings_flags.get("memory_evidence_assist_enabled", False):
                    entry["skipped_reason"] = "memory_assist_required"
                elif value and not settings_flags.get("cache_namespace_v2_enabled", False):
                    entry["skipped_reason"] = "cache_namespace_v2_required"
            deployed[flag_name] = entry

        release = file_info.get("release") or APP_RELEASE
        return {
            "app_version": release,
            "release": release,
            "git_commit": file_info.get("git_commit")
            or os.getenv("GIT_COMMIT")
            or None,
            "git_commit_short": file_info.get("git_commit_short") or None,
            "backend_commit": file_info.get("backend_commit")
            or file_info.get("git_commit")
            or os.getenv("GIT_COMMIT")
            or None,
            "frontend_commit": file_info.get("frontend_commit")
            or file_info.get("git_commit")
            or None,
            "source_ref": file_info.get("source_ref") or None,
            "build_time": file_info.get("build_time") or os.getenv("BUILD_TIME") or None,
            "alembic_head": revision,
            "memory_version": MemoryVersionService(self._db).get(),
            "knowledge_version": KnowledgeVersionService(self._db).get(),
            "feature_flags": {**env_flags, **settings_flags},
            "env_flags": env_flags,
            "settings_flags": settings_flags,
            "maintenance_observation": maint,
            "release_status": {
                "accepted": "0.9",
                "in_progress": "1.0",
                "closed_0_6": True,
                "closed_0_7": True,
                "closed_0_8": True,
                "closed_0_9": True,
                "engineering_ready": True,
                "staging_validated": False,
                "production_ready": False,
                "steps_039_045": list(RELEASE_0_6_STEPS),
                "steps_046_050": list(RELEASE_0_7_STEPS),
                # Backward-compatible alias for pre-closure consumers.
                "steps_046_048": list(RELEASE_0_7_STEPS),
                "steps_052_057": list(RELEASE_0_8_STEPS),
                "steps_058_062": list(RELEASE_0_9_STEPS),
                "steps_063": list(RELEASE_1_0_STEPS),
                "release_0_7_capabilities": {
                    "memory_region_reads": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Internal read views; no dedicated runtime flag",
                    },
                    "memory_evidence_assist": {
                        "code_present": True,
                        "enabled": bool(
                            settings_flags.get("memory_evidence_assist_enabled", False)
                        ),
                        "effective": bool(
                            deployed.get("memory_evidence_assist_enabled", {}).get(
                                "effective", False
                            )
                        ),
                    },
                    "memory_canonical_shadow": {
                        "code_present": True,
                        "enabled": bool(
                            settings_flags.get("memory_canonical_shadow_enabled", False)
                        ),
                        "effective": bool(
                            deployed.get("memory_canonical_shadow_enabled", {}).get(
                                "effective", False
                            )
                        ),
                    },
                    "memory_offline_evaluation": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Offline ops package; no runtime flag",
                    },
                },
                "release_0_8_capabilities": {
                    "settings_boost_api_removed": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Step 052 — API fields removed; ORM columns retained",
                    },
                    "dashboard_boost_inputs_removed": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Step 053 — dashboard-only",
                    },
                    "legacy_kp_presets_disabled": {
                        "code_present": True,
                        "configured": bool(
                            not settings_flags.get("allow_legacy_kp_presets", False)
                        ),
                        "enabled": bool(
                            settings_flags.get("allow_legacy_kp_presets", False)
                        ),
                        "effective": bool(
                            settings_flags.get("allow_legacy_kp_presets", False)
                        ),
                        "note": (
                            "Step 054 — default false → preset APIs 410. "
                            "configured=true means presets disabled (desired default). "
                            "code_present ≠ live DB column until migration 0018 applied."
                        ),
                    },
                    "legacy_doc_type_canonical_gated": {
                        "code_present": True,
                        "configured": bool(
                            settings_flags.get(
                                "legacy_doc_type_canonical_enabled", False
                            )
                        ),
                        "enabled": bool(
                            settings_flags.get(
                                "legacy_doc_type_canonical_enabled", False
                            )
                        ),
                        "effective": bool(
                            settings_flags.get(
                                "legacy_doc_type_canonical_enabled", False
                            )
                        ),
                        "note": (
                            "Step 055 — default false skips doc-type reorder. "
                            "Overview/news quality risk when false. "
                            "code_present ≠ live DB column until migration 0019 applied."
                        ),
                    },
                    "golden_generic_profile_ci": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Step 056 — CI/test only; production profiles unaffected",
                    },
                },
                "release_0_9_capabilities": {
                    "maintenance_agenda_ranking": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Step 058 — ephemeral ranking only; no execution",
                    },
                    "maintenance_cycle_orchestration": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": (
                            "Step 059 — env MAINTENANCE_EXECUTION_ENABLED default OFF; "
                            "budget fail-closed"
                        ),
                    },
                    "index_integrate_compose": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": (
                            "Authoritative Index→Integrate contract — opt-in compose; "
                            "index-only callers unchanged"
                        ),
                    },
                    "investigation_execution_fetch": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": (
                            "Step 060 — fetch-only investigations via Index→Integrate; "
                            "gated by Step 059"
                        ),
                    },
                    "investigation_metrics": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": (
                            "Step 061 — three process-local counters on /api/metrics; "
                            "kos_tension_resolved_total deferred"
                        ),
                    },
                    "release_0_9_engineering_closure": {
                        "code_present": True,
                        "enabled": None,
                        "effective": None,
                        "note": "Step 062 — engineering closure only; no runtime subsystem",
                    },
                },
                "note": (
                    "Release 0.9 accepted; Release 1.0 in progress (Step 063 — "
                    "knowledge_os flags default ON). "
                    "APP_RELEASE remains 0.9 until 1.0 engineering closure. "
                    "Legacy flags allow_legacy_kp_presets / "
                    "legacy_doc_type_canonical_enabled stay default OFF. "
                    "MAINTENANCE_EXECUTION_ENABLED default ON when unset; "
                    "budget still defaults to 0 (no work). "
                    "staging_validated=false; production_ready=false. "
                    "code_present ≠ configured ≠ enabled ≠ effective ≠ deployed. "
                    "Live /api/build reflects this metadata only after approved deploy+restart."
                ),
            },
            "deployed_capabilities": deployed,
        }
