#!/usr/bin/env python3
"""S001 FE remediation — single provenance writer/verifier + identity stamp.

Law: docs/releases/S001-frontend-deployment-remediation-package-amendment.md Part 3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
PROVENANCE_NAME = ".frontend-provenance.json"
IDENTITY_NAME = ".deploy-identity.json"
ASSET_REF_RE = re.compile(
    r"""(?:src|href)\s*=\s*["'](/assets/[^"']+)["']""",
    re.IGNORECASE,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_tree_sha256(index_sha: str, assets: list[dict[str, str]]) -> str:
    lines = [f"index.html\0{index_sha}"]
    for item in sorted(assets, key=lambda a: a["path"]):
        lines.append(f"{item['path']}\0{item['sha256']}")
    payload = "\n".join(lines) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _collect_assets(dist: Path) -> list[dict[str, str]]:
    assets_dir = dist / "assets"
    if not assets_dir.is_dir():
        return []
    out: list[dict[str, str]] = []
    for path in sorted(assets_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dist).as_posix()
        out.append({"path": rel, "sha256": _sha256_file(path)})
    return out


def _index_references(index_html: str) -> list[str]:
    refs = ASSET_REF_RE.findall(index_html)
    # Normalize to paths relative to dist (strip leading slash)
    normalized: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        path = ref.lstrip("/")
        if path not in seen:
            seen.add(path)
            normalized.append(path)
    return normalized


def write_provenance(dist: Path, git_commit: str, release: str, build_time: str) -> dict:
    index = dist / "index.html"
    if not index.is_file():
        raise SystemExit(f"ERROR: missing {index}")
    index_html = index.read_text(encoding="utf-8", errors="replace")
    index_sha = _sha256_file(index)
    assets = _collect_assets(dist)
    refs = _index_references(index_html)
    tree_sha = _canonical_tree_sha256(index_sha, assets)
    short = git_commit[:7] if len(git_commit) >= 7 else git_commit
    payload = {
        "schema_version": SCHEMA_VERSION,
        "git_commit": git_commit,
        "git_commit_short": short,
        "release": release,
        "build_time": build_time,
        "index_html_sha256": index_sha,
        "assets": assets,
        "index_references": refs,
        "tree_sha256": tree_sha,
    }
    out = dist / PROVENANCE_NAME
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: frontend provenance → {out}")
    return payload


def verify_provenance(dist: Path, expected_commit: str | None = None) -> dict:
    prov_path = dist / PROVENANCE_NAME
    if not prov_path.is_file():
        raise SystemExit(f"ERROR: missing provenance {prov_path}")
    try:
        data = json.loads(prov_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid provenance JSON: {exc}") from exc

    if data.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(
            f"ERROR: provenance schema_version {data.get('schema_version')!r} != {SCHEMA_VERSION}"
        )

    if expected_commit and data.get("git_commit") != expected_commit:
        raise SystemExit(
            f"ERROR: provenance git_commit ({data.get('git_commit')}) != expected ({expected_commit})"
        )

    index = dist / "index.html"
    if not index.is_file():
        raise SystemExit(f"ERROR: missing {index}")
    index_sha = _sha256_file(index)
    if index_sha != data.get("index_html_sha256"):
        raise SystemExit("ERROR: index.html sha256 mismatch vs provenance")

    assets_listed = data.get("assets")
    if not isinstance(assets_listed, list):
        raise SystemExit("ERROR: provenance assets must be a list")

    listed_paths: set[str] = set()
    for item in assets_listed:
        if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
            raise SystemExit("ERROR: provenance asset entry must have path and sha256")
        rel = item["path"]
        listed_paths.add(rel)
        file_path = dist / rel
        if not file_path.is_file():
            raise SystemExit(f"ERROR: missing asset listed in provenance: {rel}")
        actual = _sha256_file(file_path)
        if actual != item["sha256"]:
            raise SystemExit(f"ERROR: sha256 mismatch for {rel}")

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        for path in assets_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(dist).as_posix()
            if rel not in listed_paths:
                raise SystemExit(f"ERROR: orphan asset not in provenance: {rel}")

    refs = data.get("index_references")
    if not isinstance(refs, list):
        raise SystemExit("ERROR: provenance index_references must be a list")
    for ref in refs:
        if not isinstance(ref, str):
            raise SystemExit("ERROR: index_references entries must be strings")
        if ref not in listed_paths:
            raise SystemExit(f"ERROR: index reference not in assets list: {ref}")
        if not (dist / ref).is_file():
            raise SystemExit(f"ERROR: index reference missing on disk: {ref}")

    recomputed = _canonical_tree_sha256(index_sha, list(assets_listed))
    if recomputed != data.get("tree_sha256"):
        raise SystemExit("ERROR: tree_sha256 mismatch vs recomputed")

    print(f"OK: frontend provenance verified → {prov_path}")
    return data


def stamp_identity(dist: Path, git_commit: str, release: str) -> None:
    """Stamp identity only after provenance verification of dist PASS."""
    data = verify_provenance(dist, expected_commit=git_commit)
    short = git_commit[:7] if len(git_commit) >= 7 else git_commit
    payload = {
        "git_commit": git_commit,
        "git_commit_short": short,
        "release": release,
        "artifact": "dashboard/dist",
        "provenance_tree_sha256": data["tree_sha256"],
    }
    out = dist / IDENTITY_NAME
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: frontend identity → {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Frontend provenance + identity stamp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="Write .frontend-provenance.json")
    w.add_argument("--dist", required=True)
    w.add_argument("--commit", required=True)
    w.add_argument("--release", required=True)
    w.add_argument("--build-time", required=True)

    v = sub.add_parser("verify", help="Verify provenance against dist tree")
    v.add_argument("--dist", required=True)
    v.add_argument("--expected-commit", default="")

    s = sub.add_parser("stamp", help="Verify provenance then write .deploy-identity.json")
    s.add_argument("--dist", required=True)
    s.add_argument("--commit", required=True)
    s.add_argument("--release", required=True)

    args = parser.parse_args()
    dist = Path(args.dist)

    if args.cmd == "write":
        write_provenance(dist, args.commit, args.release, args.build_time)
    elif args.cmd == "verify":
        expected = args.expected_commit or None
        verify_provenance(dist, expected_commit=expected)
    elif args.cmd == "stamp":
        stamp_identity(dist, args.commit, args.release)
    else:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
