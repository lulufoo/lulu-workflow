#!/usr/bin/env python3
"""Shared schema for holder ``decision-package.json`` delivery.

Delivery shape (v2): ``status`` + ``main.decision_doc_path``. One package
delivers exactly one decision document.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_VERSION = 2
DECISION_PACKAGE_FILENAME = "decision-package.json"
_KEYS = frozenset({"version", "status", "main"})
_MAIN_KEYS = frozenset({"decision_doc_path"})


def _rel_path_ok(raw: str) -> bool:
    text = str(raw).strip()
    if not text or text.startswith("/"):
        return False
    return ".." not in Path(text).parts


def build_decision_package(
    main: dict[str, str],
    status: str = "package_ready",
    version: int = PACKAGE_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "status": str(status).strip(),
        "main": dict(main),
    }


def validate_decision_package(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["decision-package must be an object"]
    errors: list[str] = []
    if data.get("version") != PACKAGE_VERSION:
        errors.append(f"version must be {PACKAGE_VERSION}")
    extra = sorted(set(data) - _KEYS)
    if extra:
        errors.append(f"decision-package unexpected keys: {extra}")
    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        errors.append("status must be a non-empty string")
    main = data.get("main")
    if not isinstance(main, dict):
        errors.append("main must be an object")
    else:
        extra_main = sorted(set(main) - _MAIN_KEYS)
        if extra_main:
            errors.append(f"main unexpected keys: {extra_main}")
        if not _rel_path_ok(str(main.get("decision_doc_path", ""))):
            errors.append(
                "main.decision_doc_path must be a relative path under holder root"
            )
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
