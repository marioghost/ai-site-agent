"""Read boolean settings with ORM/server defaults when the row field is unset."""
from __future__ import annotations

from app.models.settings import Settings


def setting_bool(settings: Settings, name: str, default: bool = True) -> bool:
    val = getattr(settings, name, None)
    if val is None:
        return default
    return bool(val)
