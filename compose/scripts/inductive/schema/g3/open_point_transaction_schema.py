#!/usr/bin/env python3
"""Schema and I/O for slice ``_open-point-txn.json``.

Written only by the store while the caller already holds compose_state_lock.

Design rationale:
docs/domain/archive/compose/archive-34.0/compose-g3-open-point-loop-refactor-design.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parents[3] / "_kernel"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

TXN_BASENAME = "_open-point-txn.json"
TXN_VERSION = 1
_ENVELOPE_KEYS = frozenset({"version", "operation", "targets"})
_TARGET_KEYS = frozenset({"existed", "before", "after_digest"})
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def open_point_txn_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / TXN_BASENAME


def validate_open_point_txn(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["open-point-txn root must be an object"]
    errors: list[str] = []
    extra = set(data) - _ENVELOPE_KEYS
    if extra:
        errors.append(f"open-point-txn unexpected fields {sorted(extra)}")
    if data.get("version") != TXN_VERSION:
        errors.append("open-point-txn.version must be 1")
    operation = data.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        errors.append("open-point-txn.operation must be a non-empty string")
    targets = data.get("targets")
    if not isinstance(targets, dict):
        errors.append("open-point-txn.targets must be an object")
        return errors
    if not targets:
        errors.append("open-point-txn.targets must not be empty")
    for key, target in targets.items():
        prefix = f"targets[{key!r}]"
        if not isinstance(key, str) or not key.strip():
            errors.append("target keys must be non-empty path names")
        if not isinstance(target, dict):
            errors.append(f"{prefix} must be an object")
            continue
        extra_target = set(target) - _TARGET_KEYS
        if extra_target:
            errors.append(f"{prefix} unexpected fields {sorted(extra_target)}")
        for field in _TARGET_KEYS:
            if field not in target:
                errors.append(f"{prefix} missing required field {field!r}")
        if "existed" in target and not isinstance(target.get("existed"), bool):
            errors.append(f"{prefix}.existed must be a bool")
        if target.get("existed") is False and target.get("before") is not None:
            errors.append(f"{prefix}.before must be null when existed is false")
        digest = target.get("after_digest")
        if not isinstance(digest, str) or not _HEX64_RE.match(digest):
            errors.append(f"{prefix}.after_digest must be a lowercase SHA-256 hex digest")
    return errors


def normalize_open_point_txn(data: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    for key, target in (data.get("targets") or {}).items():
        if not isinstance(target, dict):
            continue
        targets[str(key)] = {
            "existed": bool(target.get("existed")),
            "before": target.get("before"),
            "after_digest": str(target.get("after_digest") or ""),
        }
    return {
        "version": TXN_VERSION,
        "operation": str(data.get("operation") or "").strip(),
        "targets": targets,
    }


def load_open_point_txn(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid open-point-txn JSON: {exc}") from exc
    errors = validate_open_point_txn(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_open_point_txn(data)


def save_open_point_txn(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = validate_open_point_txn(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_open_point_txn(data)
    errors = validate_open_point_txn(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized
