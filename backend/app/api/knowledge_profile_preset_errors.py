"""Stable HTTP error contract for disabled legacy Knowledge Profile presets (RFC-100 Step 054)."""
from __future__ import annotations

from fastapi import HTTPException

LEGACY_KP_PRESETS_DISABLED_CODE = "legacy_kp_presets_disabled"
LEGACY_KP_PRESETS_DISABLED_MESSAGE = (
    "Legacy Knowledge Profile presets are disabled."
)

LEGACY_KP_PRESETS_DISABLED_DETAIL = {
    "code": LEGACY_KP_PRESETS_DISABLED_CODE,
    "message": LEGACY_KP_PRESETS_DISABLED_MESSAGE,
}


def raise_legacy_kp_presets_disabled() -> None:
    """Raise HTTP 410 Gone with the canonical Step 054 detail payload."""
    raise HTTPException(status_code=410, detail=LEGACY_KP_PRESETS_DISABLED_DETAIL)
