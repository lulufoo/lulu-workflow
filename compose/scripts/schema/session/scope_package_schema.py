#!/usr/bin/env python3
"""scope-package.json: the single atomic input of one compose revision.

Holder adapters write it from their upstream delivered artifact; compose only
reads ``source_path`` from here and never inspects the upstream package shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCOPE_PACKAGE_FILENAME = "scope-package.json"
PACKAGE_VERSION = 2
_KEYS = frozenset({"version", "source_path", "source_id", "title"})
_REQUIRED = frozenset({"version", "source_path"})


def build_scope_package(
    *,
    source_path: str,
    source_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    package: dict[str, Any] = {"version": PACKAGE_VERSION, "source_path": str(source_path)}
    if source_id:
        package["source_id"] = str(source_id)
    if title:
        package["title"] = str(title)
    return package


def validate_scope_package(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["scope-package must be an object"]
    errors: list[str] = []
    missing = sorted(_REQUIRED - set(data))
    if missing:
        errors.append(f"scope-package missing keys: {', '.join(missing)}")
    extra = sorted(set(data) - _KEYS)
    if extra:
        errors.append(f"scope-package has unknown keys: {', '.join(extra)}")
    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"scope-package.version must be {PACKAGE_VERSION}")
    source = data.get("source_path")
    if not isinstance(source, str) or not source.strip():
        errors.append("scope-package.source_path must be a non-empty string")
    for key in ("source_id", "title"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            errors.append(f"scope-package.{key} must be a non-empty string when present")
    return errors


def scope_package_path(revision_dir: Path) -> Path:
    return Path(revision_dir).resolve() / SCOPE_PACKAGE_FILENAME


def save_scope_package(revision_dir: Path, package: dict[str, Any]) -> Path:
    errors = validate_scope_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    path = scope_package_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def load_scope_package(path: Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"scope-package.json not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    errors = validate_scope_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def is_scope_package_path(path: Path | str) -> bool:
    return Path(str(path)).name == SCOPE_PACKAGE_FILENAME


def scope_source_path(package: dict[str, Any], *, project_root: Path | None = None) -> Path:
    """Absolute source document path; relative values resolve against project_root."""
    raw = Path(str(package["source_path"]))
    if raw.is_absolute() or project_root is None:
        return raw
    return (Path(project_root).resolve() / raw).resolve()


def revision_source_path(revision_dir: Path, *, project_root: Path | None = None) -> Path:
    """Source document of a revision, read from its scope-package.json."""
    return scope_source_path(
        load_scope_package(scope_package_path(revision_dir)), project_root=project_root
    )
