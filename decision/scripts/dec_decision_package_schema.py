#!/usr/bin/env python3
"""Shared schema for holder ``decision-package.json`` delivery.

Delivery shape: ``main`` + ordered ``slices`` (decision-fact list).
No parallel ``order`` field; no ``edges`` on the delivered package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 1
DECISION_PACKAGE_FILENAME = "decision-package.json"
_SLICE_ID_RE = re.compile(r"^D\d+$")
_MAIN_KEYS = frozenset({"decision_fact_path", "decision_doc_path"})
_SLICE_KEYS = frozenset(
    {"id", "title", "decision_fact_path", "decision_doc_path"}
)


def _rel_path_ok(raw: str) -> bool:
    text = str(raw).strip()
    if not text or text.startswith("/"):
        return False
    return ".." not in Path(text).parts


def build_decision_package(
    main: dict[str, str],
    slices: list[dict[str, Any]] | None = None,
    status: str = "package_ready",
    version: int = PACKAGE_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "status": str(status).strip(),
        "main": dict(main),
        "slices": [dict(s) for s in (slices or [])],
    }


def validate_decision_package(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["decision-package must be an object"]

    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")

    if "order" in data:
        errors.append("order must not be present (sequence is slices array order)")
    if "edges" in data:
        errors.append("edges must not be present on delivered decision-package")

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        errors.append("status must be a non-empty string")

    main = data.get("main")
    if not isinstance(main, dict):
        errors.append("main must be an object")
    else:
        extra = set(main) - _MAIN_KEYS
        if extra:
            errors.append(f"main unexpected keys: {sorted(extra)}")
        for key in ("decision_fact_path", "decision_doc_path"):
            if not _rel_path_ok(str(main.get(key, ""))):
                errors.append(f"main.{key} must be a relative path under holder root")

    slices = data.get("slices")
    if not isinstance(slices, list):
        errors.append("slices must be a list (may be empty for no-split)")
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
        if not _SLICE_ID_RE.match(sid):
            errors.append(f"{where}.id must match D<number>")
        elif sid in seen:
            errors.append(f"slices duplicate id {sid!r}")
        else:
            seen.add(sid)
        if not str(row.get("title", "")).strip():
            errors.append(f"{where}.title must be non-empty")
        for key in ("decision_fact_path", "decision_doc_path"):
            if not _rel_path_ok(str(row.get(key, ""))):
                errors.append(f"{where}.{key} must be a relative path under holder root")

    return errors


def save_decision_package(holder_root: Path, package: dict[str, Any]) -> Path:
    errors = validate_decision_package(package)
    if errors:
        raise ValueError("; ".join(errors))
    path = Path(holder_root) / DECISION_PACKAGE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_decision_package(path: Path) -> dict[str, Any]:
    package_path = Path(path)
    if not package_path.is_file():
        raise FileNotFoundError(f"missing decision-package: {package_path}")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    errors = validate_decision_package(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def is_decision_package_path(path: Path | str) -> bool:
    return Path(path).name == DECISION_PACKAGE_FILENAME
