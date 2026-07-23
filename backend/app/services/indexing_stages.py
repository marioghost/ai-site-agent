"""Stable indexing stage codes for status API and UI."""
from __future__ import annotations

STAGE_IDLE = "idle"
STAGE_PREPARING = "preparing"
STAGE_DISCOVERING_URLS = "discovering_urls"
STAGE_PLANNING_QUEUE = "planning_queue"
STAGE_FETCHING_PAGE = "fetching_page"
STAGE_EXTRACTING_TEXT = "extracting_text"
STAGE_CHUNKING = "chunking"
STAGE_EMBEDDING = "embedding"
STAGE_SAVING = "saving"
STAGE_CHECKING_FILE = "checking_file"
STAGE_COMPLETED = "completed"
STAGE_STOPPED = "stopped"
STAGE_FAILED = "failed"

# Legacy worker phase -> canonical stage (when stage not stored in progress_json)
PHASE_TO_STAGE: dict[str, str] = {
    "idle": STAGE_IDLE,
    "discovery": STAGE_DISCOVERING_URLS,
    "planning": STAGE_PLANNING_QUEUE,
    "processing_pages": STAGE_FETCHING_PAGE,
    "processing_files": STAGE_CHECKING_FILE,
    "selecting_sources": STAGE_PREPARING,
    "analyzing_sources": "analyzing_sources",
    "updating_profiles": "updating_profiles",
    "previewing": "previewing",
    "detecting_boilerplate": STAGE_PREPARING,
    "loading_source": STAGE_FETCHING_PAGE,
    "rebuilding_chunks": STAGE_CHUNKING,
    "invalidating_cache": STAGE_SAVING,
    "complete": STAGE_COMPLETED,
    "completed": STAGE_COMPLETED,
    "stopped": STAGE_STOPPED,
    "failed": STAGE_FAILED,
}


def resolve_stage(stage: str | None, current_phase: str | None) -> str:
    if stage:
        return stage
    if current_phase:
        return PHASE_TO_STAGE.get(current_phase, current_phase)
    return STAGE_IDLE
