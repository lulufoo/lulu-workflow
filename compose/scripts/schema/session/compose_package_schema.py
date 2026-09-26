#!/usr/bin/env python3
"""Schema and I/O for revision ``*-package.json`` (compose delivery marker).

Cross-stage delivery entry is this JSON only; prose stays at ``execution/*-doc.md``.
Shape (v2)::

    {
      "version": 2,
      "profile_id": "lulu-design",
      "doc_path": "execution/design-doc.md"
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 2
_KEYS = frozenset({"version", "profile_id", "doc_path"})


def package_filename_from_doc(doc_filename: str) -> str:
    """Derive delivery package name from ``document.filename``.

    ``design-doc.md`` → ``design-package.json``; ``tech-doc.md`` → ``tech-package.json``.
    """
    name = str(doc_filename).strip()
    if not name:
        raise ValueError("doc_filename must be non-empty")
    if name.endswith("-doc.md"):
        return f"{name[: -len('-doc.md')]}-package.json"
    if name.endswith(".md"):
        return f"{name[:-3]}-package.json"
    if name.endswith(".json"):
        return name if name.endswith("-package.json") else f"{name[:-5]}-package.json"
    return f"{name}-package.json"


def compose_package_path(revision_dir: Path, doc_filename: str) -> Path:
    return Path(revision_dir) / package_filename_from_doc(doc_filename)


def build_compose_package(*, profile_id: str, doc_path: str) -> dict[str, Any]:
    return {
        "version": PACKAGE_VERSION,
        "profile_id": str(profile_id).strip(),
        "doc_path": str(doc_path).strip(),
    }


def validate_compose_package(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["package must be an object"]
    errors: list[str] = []
    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")
    extra = sorted(set(data) - _KEYS)
    if extra:
        errors.append(f"package has unknown keys: {', '.join(extra)}")
    profile_id = data.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        errors.append("profile_id must be a non-empty string")
    doc_path = str(data.get("doc_path", "")).strip()
    if not doc_path or doc_path.startswith("/") or ".." in Path(doc_path).parts:
        errors.append("doc_path must be a relative path under the revision root")
    return errors


def package_doc_path(package: dict[str, Any], *, package_path: Path) -> Path:
    """Absolute prose path referenced by a loaded package."""
    rel = str(package.get("doc_path", "")).strip()
    return (Path(package_path).resolve().parent / rel).resolve()


def missing_doc(revision_dir: Path, package: dict[str, Any]) -> str | None:
    rel = str(package.get("doc_path", "")).strip()
    if rel and (Path(revision_dir) / rel).is_file():
        return None
    return rel or "<empty doc_path>"


def save_compose_package(revision_dir: Path, doc_filename: str, package: dict[str, Any]) -> Path:
    errors = validate_compose_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    missing = missing_doc(revision_dir, package)
    if missing is not None:
        raise ValueError(f"missing doc: {missing}")
    path = compose_package_path(revision_dir, doc_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_compose_package(path: Path) -> dict[str, Any]:
    package_path = Path(path)
    if not package_path.is_file():
        raise FileNotFoundError(f"missing compose package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    errors = validate_compose_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def validate_committed_package(
    revision_dir: Path,
    *,
    doc_filename: str,
    profile_id: str,
    expected_doc_path: str,
) -> tuple[Path | None, str | None]:
    """Check an existing Ready package against the profile and prose. Never writes."""
    rev = Path(revision_dir).resolve()
    path = compose_package_path(rev, doc_filename)
    if not path.is_file():
        return None, "Ready package missing"
    try:
        package = load_compose_package(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if str(package.get("profile_id", "")).strip() != str(profile_id).strip():
        return None, f"package profile_id {package.get('profile_id')!r} != {profile_id!r}"
    if str(package.get("doc_path", "")).strip() != str(expected_doc_path).strip():
        return None, f"package doc_path {package.get('doc_path')!r} != {expected_doc_path!r}"
    missing = missing_doc(rev, package)
    if missing is not None:
        return None, f"missing doc: {missing}"
    return path, None


def is_compose_package_path(path: Path | str) -> bool:
    return Path(path).name.endswith("-package.json")
