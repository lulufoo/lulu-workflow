#!/usr/bin/env python3
"""Schema and I/O for revision ``slice-rulers.json`` (multi-subdesign split).

Shape::

    {
      "version": 1,
      "status": "draft" | "locked",
      "cut_axis": "tech_domain" | "business_domain" | "runtime_tier" | <custom>,
      "rulers": {
        "L1": {
          "id": "L1",
          "job": "...",
          "in": ["..."],
          "out": ["..."],
          "seam": [{"with": "L2", "owns": "full_plan"|"depend_only", "note": "..."}],
          "plan_checklist": ["..."]
        }
      }
    }

Multi-L (n>=2): every tree node id must have a ruler when status=locked.
Single-L (L1 only): file may be absent (exempt).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SLICE_RULERS_FILENAME = "slice-rulers.json"
SLICE_RULERS_VERSION = 1
_VALID_STATUS = frozenset({"draft", "locked"})
_NODE_ID_RE = re.compile(r"^L\d+$")
_OWN_VALUES = frozenset({"full_plan", "depend_only"})
_RULER_KEYS = frozenset({"id", "job", "in", "out", "seam", "plan_checklist"})
_SEAM_KEYS = frozenset({"with", "owns", "note"})


def slice_rulers_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / SLICE_RULERS_FILENAME


def build_slice_rulers(
    *,
    cut_axis: str,
    rulers: dict[str, dict[str, Any]],
    status: str = "draft",
    version: int = SLICE_RULERS_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "status": str(status),
        "cut_axis": str(cut_axis).strip(),
        "rulers": {str(k): dict(v) for k, v in rulers.items()},
    }


def validate_slice_rulers(
    data: dict[str, Any],
    *,
    required_node_ids: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["slice-rulers must be an object"]

    if data.get("version") != SLICE_RULERS_VERSION:
        errors.append(f"version must be {SLICE_RULERS_VERSION}")

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
            errors.append(f"{where}: key must match L<number>")
        if not isinstance(ruler, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(ruler) - _RULER_KEYS
        if extra:
            errors.append(f"{where} unexpected keys: {sorted(extra)}")
        rid = str(ruler.get("id", "")).strip()
        if rid != str(nid):
            errors.append(f"{where}.id must equal key {nid!r} (got {rid!r})")
        if not str(ruler.get("job", "")).strip():
            errors.append(f"{where}.job must be non-empty")
        for list_key in ("in", "out", "plan_checklist"):
            arr = ruler.get(list_key)
            if not isinstance(arr, list) or not arr:
                errors.append(f"{where}.{list_key} must be a non-empty array")
            else:
                for i, item in enumerate(arr):
                    if not isinstance(item, str) or not item.strip():
                        errors.append(
                            f"{where}.{list_key}[{i}] must be a non-empty string"
                        )
        seams = ruler.get("seam")
        if not isinstance(seams, list):
            errors.append(f"{where}.seam must be an array")
            continue
        for i, seam in enumerate(seams):
            sw = f"{where}.seam[{i}]"
            if not isinstance(seam, dict):
                errors.append(f"{sw} must be an object")
                continue
            sextra = set(seam) - _SEAM_KEYS
            if sextra:
                errors.append(f"{sw} unexpected keys: {sorted(sextra)}")
            with_id = str(seam.get("with", "")).strip()
            if not _NODE_ID_RE.match(with_id):
                errors.append(f"{sw}.with must match L<number>")
            owns = str(seam.get("owns", "")).strip()
            if owns not in _OWN_VALUES:
                errors.append(f"{sw}.owns must be full_plan|depend_only")
            if not str(seam.get("note", "")).strip():
                errors.append(f"{sw}.note must be non-empty")

    # Dual-SSOT: conflicting owns on the same undirected seam pair
    owns_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for nid, ruler in rulers.items():
        if not isinstance(ruler, dict):
            continue
        for seam in ruler.get("seam") or []:
            if not isinstance(seam, dict):
                continue
            a, b = str(nid), str(seam.get("with", "")).strip()
            if not a or not b:
                continue
            pair = tuple(sorted((a, b)))
            owns_by_pair.setdefault(pair, {})[a] = str(seam.get("owns", "")).strip()
    for pair, mapping in owns_by_pair.items():
        if len(mapping) < 2:
            continue
        vals = list(mapping.values())
        if vals[0] == "full_plan" and vals[1] == "full_plan":
            errors.append(
                f"seam {pair[0]}↔{pair[1]}: both sides owns=full_plan (dual SSOT)"
            )

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


def save_slice_rulers(revision_dir: Path, data: dict[str, Any]) -> Path:
    errors = validate_slice_rulers(data)
    if errors:
        raise ValueError("; ".join(errors))
    path = slice_rulers_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_slice_rulers(revision_dir: Path) -> dict[str, Any]:
    path = slice_rulers_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing slice rulers: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_slice_rulers(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data
