"""Phase 0 does not wire understanding into retrieval ranking (shadow is Phase 1)."""
from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_pipeline_modules_do_not_import_kul():
    roots = [
        Path(__file__).resolve().parents[1] / "app/services/retrieval_engine",
        Path(__file__).resolve().parents[1] / "app/services/evidence_planning",
    ]
    offenders: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "knowledge_understanding" in text:
                offenders.append(str(path))
    assert not offenders, f"KUL leaked into frozen retrieval path: {offenders}"
