"""Deployment corpus boundary resolution for Memory region reads (Step 046 extension).

Resolves which Source rows belong to the configured deployment corpus.
Does not inspect queries, rank sources, or perform retrieval.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.source import Source
from app.services.epistemic_memory.memory_region_types import MemoryCorpusScope
from app.utils.url_utils import get_domain, is_allowed_domain

if TYPE_CHECKING:
    from app.models.settings import Settings

CORPUS_BOUNDARY_VERSION = "v1"
_DIAGNOSTIC_SOURCE_ID_CAP = 200


@dataclass(frozen=True)
class MemoryCorpusBoundary:
    """Immutable deployment corpus boundary derived from Settings."""

    corpus_scope: MemoryCorpusScope | None
    hosts: tuple[str, ...]
    configured: bool
    invalid_entries: tuple[str, ...]
    settings_row_id: int | None
    complete: bool = True

    def fingerprint(self) -> str:
        """Deterministic boundary fingerprint for Step 047 cache identity."""
        import hashlib

        payload = "|".join(
            [
                CORPUS_BOUNDARY_VERSION,
                self.corpus_scope.value if self.corpus_scope else "",
                ",".join(self.hosts),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_allowed_host_entry(raw: str) -> str | None:
    """Normalize a settings host/domain entry to a lowercase host."""
    text = (raw or "").strip()
    if not text:
        return None
    if "://" in text or text.startswith("//"):
        try:
            host = get_domain(text if "://" in text else f"https://{text}")
        except Exception:
            return None
    else:
        host = text.split("/")[0].split(":")[0].strip().lower()
    host = host.rstrip(".")
    if not host or " " in host or "/" in host:
        return None
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    return host


def resolve_deployment_boundary(settings: Settings | None) -> MemoryCorpusBoundary:
    """Resolve deployment hosts from the canonical Settings row (lowest id)."""
    settings_row_id = settings.id if settings is not None else None
    hosts: list[str] = []
    invalid: list[str] = []

    allowed_raw: list[str] = []
    if settings is not None:
        try:
            parsed = json.loads(settings.allowed_domains_json or "[]")
            if isinstance(parsed, list):
                allowed_raw = [str(x) for x in parsed]
        except (json.JSONDecodeError, TypeError):
            invalid.append("allowed_domains_json")

    for entry in allowed_raw:
        normalized = normalize_allowed_host_entry(entry)
        if normalized:
            hosts.append(normalized)
        else:
            invalid.append(entry)

    if not hosts and settings is not None and settings.site_url:
        site_host = normalize_allowed_host_entry(settings.site_url)
        if site_host:
            hosts.append(site_host)
        else:
            invalid.append(settings.site_url)

    unique_hosts = tuple(sorted(set(hosts)))
    configured = bool(unique_hosts)
    return MemoryCorpusBoundary(
        corpus_scope=MemoryCorpusScope.DEPLOYMENT if configured else None,
        hosts=unique_hosts,
        configured=configured,
        invalid_entries=tuple(invalid),
        settings_row_id=settings_row_id,
        complete=True,
    )


def _sql_host_expr(url_column):
    """PostgreSQL host extraction from stored source URL."""
    stripped = func.regexp_replace(url_column, r"^https?://", "", "i")
    host_with_port = func.lower(func.split_part(stripped, "/", 1))
    return func.split_part(host_with_port, ":", 1)


def _host_match_conditions(allowed_hosts: tuple[str, ...]):
    host_expr = _sql_host_expr(Source.url)
    clauses = []
    for host in allowed_hosts:
        clauses.append(host_expr == host)
        clauses.append(host_expr.like(f"%.{host}"))
    return or_(*clauses) if clauses else None


def resolve_corpus_source_ids(
    db: Session,
    boundary: MemoryCorpusBoundary,
) -> tuple[int, ...]:
    """Return all Source IDs whose URL host matches the deployment boundary."""
    if not boundary.configured or not boundary.hosts:
        return ()
    condition = _host_match_conditions(boundary.hosts)
    if condition is None:
        return ()
    rows = db.scalars(
        select(Source.id).where(condition).order_by(Source.id.asc())
    ).all()
    return tuple(rows)


def source_url_allowed(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    """Match a source URL against allowed hosts using crawler subdomain semantics."""
    return is_allowed_domain(url, list(allowed_hosts))


def bounded_diagnostic_source_ids(source_ids: tuple[int, ...]) -> tuple[int, ...]:
    """Cap diagnostic source ID lists without affecting query completeness."""
    if len(source_ids) <= _DIAGNOSTIC_SOURCE_ID_CAP:
        return source_ids
    return source_ids[:_DIAGNOSTIC_SOURCE_ID_CAP]
