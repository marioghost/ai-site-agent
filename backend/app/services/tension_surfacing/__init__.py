"""Tension surfacing — read-only detection (RFC-100 Step 034)."""
from app.services.tension_surfacing.tension_surfacing_service import (
    METRICS_CLAIM_SCAN_LIMIT,
    TensionCountSummary,
    TensionSurfacingService,
)
from app.services.tension_surfacing.tension_types import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

__all__ = [
    "METRICS_CLAIM_SCAN_LIMIT",
    "TENSION_CONFLICT",
    "TENSION_SUPPORT_DEFICIT",
    "TensionCountSummary",
    "TensionSurfacingService",
    "TensionView",
]
