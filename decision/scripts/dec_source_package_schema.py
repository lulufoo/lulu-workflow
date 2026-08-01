#!/usr/bin/env python3
"""Shared schema for a decision holder's ``source-package.json`` delivery."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 1
SOURCE_PACKAGE_FILENAME = "source-package.json"
_SLICE_ID_RE = re.compile(r"^L\d+$")
_PACKAGE_KEYS = frozenset({"version", "holder_stage", "slices", "commit_status"})
_SLICE_KEYS = frozenset({"id", "title", "source_path", "source_id"})
_COMMIT_STATUSES = frozenset({"prepared", "committed"})


def _rel_path_ok(raw: str) -> bool:
    text = str(raw).strip()
    return bool(text) and not text.startswith("/") and ".." not in Path(text).parts


def build_source_package(
    *,
    holder_stage: str,
    slices: list[dict[str, Any]],
    commit_status: str = "prepared",
    version: int = PACKAGE_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "holder_stage": str(holder_stage).strip(),
        "slices": [dict(row) for row in slices],
        "commit_status": str(commit_status).strip(),
    }


def validate_source_package(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["source-package must be an object"]

    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")
    extra = set(data) - _PACKAGE_KEYS
    if extra:
        errors.append(f"unexpected keys: {sorted(extra)}")
    if not str(data.get("holder_stage", "")).strip():
        errors.append("holder_stage must be a non-empty string")
    if data.get("commit_status") not in _COMMIT_STATUSES:
        errors.append(f"commit_status must be one of {sorted(_COMMIT_STATUSES)}")

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
        slice_id = str(row.get("id", "")).strip()
        if not _SLICE_ID_RE.match(slice_id):
            errors.append(f"{where}.id must match L<number>")
        elif slice_id in seen:
            errors.append(f"slices duplicate id {slice_id!r}")
        else:
            seen.add(slice_id)
        if not str(row.get("title", "")).strip():
            errors.append(f"{where}.title must be non-empty")
        if not _rel_path_ok(str(row.get("source_path", ""))):
            errors.append(
                f"{where}.source_path must be a relative path under holder root"
            )
        if not str(row.get("source_id", "")).strip():
            errors.append(f"{where}.source_id must be non-empty")
    return errors


def save_source_package(holder_root: Path, package: dict[str, Any]) -> Path:
    errors = validate_source_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    path = Path(holder_root) / SOURCE_PACKAGE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_source_package(path: Path) -> dict[str, Any]:
    package_path = Path(path)
    if not package_path.is_file():
        raise FileNotFoundError(f"missing source-package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    errors = validate_source_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def is_source_package_path(path: Path | str) -> bool:
    return Path(path).name == SOURCE_PACKAGE_FILENAME
