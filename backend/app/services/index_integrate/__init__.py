"""Additive Index → Integrate compose contract."""

from app.services.index_integrate.compose import index_and_integrate
from app.services.index_integrate.types import IndexIntegrateResult

__all__ = ["IndexIntegrateResult", "index_and_integrate"]
