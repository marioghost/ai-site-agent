"""Zero-hardcode guard for Knowledge Understanding path."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

KUL_DIR = Path(__file__).resolve().parents[1] / "app/services/knowledge_understanding"

BANNED_SUBSTRINGS = (
    "mortgage",
    "iban",
    "swift",
    "banking",
    "кредит",
    "іпотека",
    "DOCUMENT_TYPE_BOOST",
    "PRIMARY_OVERVIEW",
    "BANK_",
    "INDUSTRY_RULES",
)


def _py_files() -> list[Path]:
    return sorted(KUL_DIR.rglob("*.py"))


def test_kul_package_exists():
    assert KUL_DIR.is_dir()
    assert (KUL_DIR / "interface.py").is_file()
    assert (KUL_DIR / "builder.py").is_file()
    assert (KUL_DIR / "adapters" / "concept_index.py").is_file()


def test_no_domain_hardcode_in_understanding_modules():
    offenders: list[str] = []
    for path in _py_files():
        text = path.read_text(encoding="utf-8").lower()
        for banned in BANNED_SUBSTRINGS:
            if banned.lower() in text:
                offenders.append(f"{path.name}:{banned}")
    assert not offenders, f"domain hardcode in KUL: {offenders}"


def test_no_synonym_regex_tables_in_normalizer():
    path = KUL_DIR / "normalizer.py"
    src = path.read_text(encoding="utf-8")
    assert "SYNONYMS" not in src
    assert "ALIAS_MAP" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and len(getattr(node, "keys", []) or []) > 8:
            raise AssertionError("unexpected large dict literal in normalizer")
