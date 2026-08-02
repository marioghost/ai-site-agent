"""Structured observability for chat dispatch (RFC-100 Step 004 / Step 064).

Logs metadata only — never prompts, answers, sources, or user content.

Step 064 path vocabulary (complete allow-list for API chat dispatch):
  executive | executive_disabled
"""
from __future__ import annotations

import logging
from typing import Literal

from app.services.feature_flags import knowledge_os_executive_enabled

ChatPath = Literal["executive", "executive_disabled"]
ChatMode = Literal["non_stream", "stream"]
StreamLifecycle = Literal["start", "end", "cancelled", "error"]


def resolve_chat_path() -> ChatPath:
    return "executive" if knowledge_os_executive_enabled() else "executive_disabled"


def log_chat_dispatch(
    logger: logging.Logger,
    *,
    request_id: str,
    mode: ChatMode,
    path: ChatPath | None = None,
    stream_lifecycle: StreamLifecycle | None = None,
    error_type: str | None = None,
    events_count: int | None = None,
    duration_ms: int | None = None,
    level: int = logging.INFO,
) -> None:
    """Emit one structured chat_dispatch log line with fixed field names."""
    path = path or resolve_chat_path()
    fields: list[str] = [
        f"request_id={request_id}",
        f"path={path}",
        f"mode={mode}",
    ]
    if stream_lifecycle is not None:
        fields.append(f"stream_lifecycle={stream_lifecycle}")
    if error_type is not None:
        fields.append(f"error_type={error_type}")
    if events_count is not None:
        fields.append(f"events_count={events_count}")
    if duration_ms is not None:
        fields.append(f"duration_ms={duration_ms}")
    logger.log(level, "chat_dispatch %s", " ".join(fields))
