"""Lightweight contradiction detection within selected evidence."""
from __future__ import annotations

import re

from app.services.evidence_planning.types import SelectedEvidence

_PRICE = re.compile(r"\b(\d[\d\s.,]{1,12})\s*(?:uah|usd|eur|₴|\$|€|грн)\b", re.I)
_DATE = re.compile(r"\b(20\d{2}|19\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b")


def detect_contradictions(selected: list[SelectedEvidence]) -> list[dict]:
    conflicts: list[dict] = []
    conflicts.extend(_price_conflicts(selected))
    conflicts.extend(_policy_version_conflicts(selected))
    return conflicts


def _price_conflicts(selected: list[SelectedEvidence]) -> list[dict]:
    prices: list[tuple[str, str]] = []
    for item in selected:
        text = item.candidate.section_text or item.candidate.text
        for match in _PRICE.findall(text):
            prices.append((item.candidate.url, match.strip()))
    unique = {p for _, p in prices}
    if len(unique) >= 2 and len(prices) >= 2:
        return [
            {
                "type": "price_conflict",
                "values": sorted(unique)[:4],
                "sources": [u for u, _ in prices[:4]],
                "resolved": False,
            }
        ]
    return []


def _policy_version_conflicts(selected: list[SelectedEvidence]) -> list[dict]:
    dated: list[tuple[str, str]] = []
    for item in selected:
        text = item.candidate.section_text or item.candidate.text
        if "policy" not in text.lower() and item.candidate.page_role != "legal":
            continue
        for match in _DATE.findall(text):
            dated.append((item.candidate.url, "-".join(match)))
    years = {d for _, d in dated}
    if len(years) >= 2:
        return [
            {
                "type": "temporal_conflict",
                "values": sorted(years)[:4],
                "sources": [u for u, _ in dated[:4]],
                "resolved": False,
            }
        ]
    return []
