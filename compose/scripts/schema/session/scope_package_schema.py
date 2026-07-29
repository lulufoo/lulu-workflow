#!/usr/bin/env python3
"""Schema for design→compose ``scope-package.json`` (archive-1.0 P0).

Ordered ``slices`` with ``L*`` ids + ``fact_path``. No ``order`` / ``edges``.
Scope SSOT is the file path, not an inline JSON string.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 1
SCOPE_PACKAGE_FILENAME = "scope-package.json"
_NODE_ID_RE = re.compile(r"^L\d+$")
_SLICE_KEYS = frozenset({"id", "title", "fact_path", "source_id"})


def _rel_or_abs_fact_ok(raw: str) -> bool:
    text = str(raw).strip()
    if not text:
        return False
    if text.startswith("/"):
        return True
    return ".." not in Path(text).parts


def build_scope_package(
    slices: list[dict[str, Any]],
    version: int = PACKAGE_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "slices": [dict(s) for s in slices],
    }


def validate_scope_package(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["scope-package must be an object"]

    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")

    if "order" in data:
        errors.append("order must not be present (sequence is slices array order)")
    if "edges" in data:
        errors.append("edges must not be present on scope-package")

    slices = data.get("slices")
    if not isinstance(slices, list) or not slices:
        errors.append("slices must be a non-empty list")
        return errors

    seen: set[str] = set()
    for idx, row in enumerate(slices):
        where = f"slices[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(row) - _SLICE_KEYS
        if extra:
            errors.append(f"{where} unexpected keys: {sorted(extra)}")
        sid = str(row.get("id", "")).strip()
        if not _NODE_ID_RE.match(sid):
            errors.append(f"{where}.id must match L<number>")
        elif sid in seen:
            errors.append(f"slices duplicate id {sid!r}")
        else:
            seen.add(sid)
        if not str(row.get("title", "")).strip():
            errors.append(f"{where}.title must be non-empty")
        if not _rel_or_abs_fact_ok(str(row.get("fact_path", ""))):
            errors.append(f"{where}.fact_path must be a non-empty path")
        source_id = row.get("source_id")
        if source_id is not None and not str(source_id).strip():
            errors.append(f"{where}.source_id if present must be non-empty")

    return errors


def save_scope_package(revision_dir: Path, package: dict[str, Any]) -> Path:
    errors = validate_scope_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    path = Path(revision_dir) / SCOPE_PACKAGE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_scope_package(path: Path) -> dict[str, Any]:
    package_path = Path(path)
    if not package_path.is_file():
        raise FileNotFoundError(f"missing scope-package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    errors = validate_scope_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def is_scope_package_path(path: Path | str) -> bool:
    return Path(path).name == SCOPE_PACKAGE_FILENAME


def chain_ids_from_scope_package(package: dict[str, Any]) -> list[str]:
    """Return L* ids in slices array order (strict chain source)."""
    return [
        str(row["id"]).strip()
        for row in package.get("slices") or []
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    ]
