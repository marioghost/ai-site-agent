"""HTTP deprecation metadata for legacy Knowledge Profile APIs (RFC-100 Step 017)."""
from __future__ import annotations

from starlette.responses import Response

# Sunset date not defined in migration docs yet — omit Sunset header until Release 0.8+.
KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK = (
    '<docs/RFC-100-PRODUCTION-MIGRATION-STRATEGY.md>; rel="deprecation"'
)


def apply_knowledge_profile_preset_load_deprecation(response: Response) -> None:
    """Attach RFC 8594-style deprecation headers to preset load responses."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = KNOWLEDGE_PROFILE_PRESET_LOAD_DEPRECATION_LINK
