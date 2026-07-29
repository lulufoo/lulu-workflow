#!/usr/bin/env python3
"""Decision-oriented rulers (archive-1.0 P2.split S2=B).

``decision-rulers.json`` at approach root. Semantics: job / boundary /
deps_summary — not compose ``seam.full_plan``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DECISION_RULERS_FILENAME = "decision-rulers.json"
DECISION_RULERS_VERSION = 1
_VALID_STATUS = frozenset({"draft", "locked"})
_NODE_ID_RE = re.compile(r"^D\d+$")
_RULER_KEYS = frozenset({"id", "job", "boundary", "deps_summary"})


def decision_rulers_path(approach_root: Path) -> Path:
    return Path(approach_root).resolve() / DECISION_RULERS_FILENAME


def build_decision_rulers(
    *,
    cut_axis: str,
    rulers: dict[str, dict[str, Any]],
    status: str = "draft",
    version: int = DECISION_RULERS_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "status": str(status),
        "cut_axis": str(cut_axis).strip(),
        "rulers": {str(k): dict(v) for k, v in rulers.items()},
    }


def validate_decision_rulers(
    data: dict[str, Any],
    *,
    required_node_ids: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["decision-rulers must be an object"]

    if data.get("version") != DECISION_RULERS_VERSION:
        errors.append(f"version must be {DECISION_RULERS_VERSION}")

    status = data.get("status")
    if status not in _VALID_STATUS:
        errors.append("status must be draft|locked")

    cut_axis = data.get("cut_axis")
    if not isinstance(cut_axis, str) or not cut_axis.strip():
        errors.append("cut_axis must be a non-empty string")

    rulers = data.get("rulers")
    if not isinstance(rulers, dict):
        errors.append("rulers must be an object")
        return errors

    for nid, ruler in rulers.items():
        where = f"rulers[{nid!r}]"
        if not _NODE_ID_RE.match(str(nid)):
            errors.append(f"{where}: key must match D<number>")
        if not isinstance(ruler, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(ruler) - _RULER_KEYS
        if extra:
            errors.append(f"{where} unexpected keys: {sorted(extra)}")
        rid = str(ruler.get("id", "")).strip()
        if rid != str(nid):
            errors.append(f"{where}.id must equal key {nid!r} (got {rid!r})")
        for field in ("job", "boundary", "deps_summary"):
            if not str(ruler.get(field, "")).strip():
                errors.append(f"{where}.{field} must be non-empty")

    if required_node_ids is not None:
        req = set(required_node_ids)
        have = set(rulers)
        missing = sorted(req - have)
        extra_ids = sorted(have - req)
        if missing:
            errors.append(f"missing rulers for nodes: {missing}")
        if extra_ids:
            errors.append(f"rulers for unknown nodes: {extra_ids}")

    return errors


def save_decision_rulers(approach_root: Path, data: dict[str, Any]) -> Path:
    errors = validate_decision_rulers(data)
    if errors:
        raise ValueError("; ".join(errors))
    path = decision_rulers_path(approach_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_decision_rulers(approach_root: Path) -> dict[str, Any]:
    path = decision_rulers_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"missing decision rulers: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_decision_rulers(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data
