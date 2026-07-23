"""Shared helpers for matching Ollama model names."""
from __future__ import annotations


def _model_aliases(name: str) -> set[str]:
    name = name.strip()
    if not name:
        return set()
    aliases = {name}
    if ":" not in name:
        aliases.add(f"{name}:latest")
    elif name.endswith(":latest"):
        aliases.add(name[: -len(":latest")])
    return aliases


def ollama_model_installed(requested: str, installed: list[str]) -> bool:
    if not requested:
        return False
    req_aliases = _model_aliases(requested)
    return any(req_aliases & _model_aliases(name) for name in installed)


def ollama_models_match(a: str, b: str) -> bool:
    return ollama_model_installed(a, [b])
