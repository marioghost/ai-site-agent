"""Tension surfacing — read-only detection (RFC-100 Step 034)."""
from app.services.tension_surfacing.tension_surfacing_service import TensionSurfacingService
from app.services.tension_surfacing.tension_types import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

__all__ = [
    "TENSION_CONFLICT",
    "TENSION_SUPPORT_DEFICIT",
    "TensionSurfacingService",
    "TensionView",
]
