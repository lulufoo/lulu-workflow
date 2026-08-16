#!/usr/bin/env python3
"""Schema and durable I/O for Human Resolution transaction journals."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HUMAN_RESOLUTION_TXN_VERSION = "1"
_DIGEST_CHARS = frozenset("0123456789abcdef")
_TARGETS = ("review_file", "evaluate_state", "operation_records")


def _valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _DIGEST_CHARS for character in value)
    )


def validate_human_resolution_txn(data: Any) -> list[str]:
    """Return validation errors for one transaction journal."""
    if not isinstance(data, dict):
        return ["transaction must be an object"]
    errors: list[str] = []
    if data.get("version") != HUMAN_RESOLUTION_TXN_VERSION:
        errors.append("invalid transaction version")
    if data.get("operation") != "submit-human-resolution":
        errors.append("invalid transaction operation")
    for field in ("dimension_token", "submission_digest"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    if data.get("phase") not in {"prepared", "applied"}:
        errors.append("phase must be prepared or applied")
    targets = data.get("targets")
    if not isinstance(targets, dict) or set(targets) != set(_TARGETS):
        errors.append("targets must contain review_file, evaluate_state, operation_records")
        return errors
    for name in _TARGETS:
        target = targets[name]
        if not isinstance(target, dict):
            errors.append(f"targets.{name} must be an object")
            continue
        if not isinstance(target.get("path"), str) or not target["path"]:
            errors.append(f"targets.{name}.path must be a non-empty string")
        if not _valid_digest(target.get("before_digest")):
            errors.append(f"targets.{name}.before_digest must be SHA-256")
        if not _valid_digest(target.get("after_digest")):
            errors.append(f"targets.{name}.after_digest must be SHA-256")
        if "before" not in target or "after" not in target:
            errors.append(f"targets.{name} requires before and after snapshots")
    return errors


def load_human_resolution_txn(path: Path) -> dict[str, Any]:
    """Load and validate one transaction journal."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Human Resolution transaction journal: {exc}") from exc
    errors = validate_human_resolution_txn(data)
    if errors:
        raise ValueError(
            f"Human Resolution transaction invalid: {'; '.join(errors)}",
        )
    return data


def save_human_resolution_txn(path: Path, data: dict[str, Any]) -> None:
    """Atomically persist one validated transaction journal."""
    errors = validate_human_resolution_txn(data)
    if errors:
        raise ValueError(
            f"Human Resolution transaction invalid: {'; '.join(errors)}",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
