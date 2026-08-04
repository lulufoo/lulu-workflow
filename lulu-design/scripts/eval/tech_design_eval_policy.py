#!/usr/bin/env python3
"""Inclusion policy for lulu-design dynamic EvalCorpus composition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_DIMENSION_DEF_FILES = {
    "codebase-consistency": "codebase-consistency.json",
    "solution-quality": "solution-quality.json",
    "intent-alignment": "intent-alignment.json",
}

_TOPIC_EVAL_BLOCKED = (
    "topic cycles do not evaluate in lulu-design; "
    "feature cycle only."
)


def select_dimension_ids(
    mode: str = "tech",
    upstream_baseline_ref: str = "",
) -> list[str]:
    """Return ordered dimension ids for lulu-design Evaluating.

    When mode='product' and upstream_baseline_ref is non-empty, intent-alignment (d3)
    is appended. Otherwise d3 is silently skipped.
    """
    ids = ["codebase-consistency", "solution-quality"]
    if mode == "product" and upstream_baseline_ref:
        ids.append("intent-alignment")
    return ids


def require_feature_eval(cycle_type: str) -> None:
    """Raise when cycle_type cannot use lulu-design Evaluating."""
    if cycle_type == "topic":
        raise ValueError(_TOPIC_EVAL_BLOCKED)
    if cycle_type != "feature":
        raise ValueError(f"unsupported cycle_type for eval: {cycle_type!r}")


def load_dimension_defs(
    dimension_defs_dir: Path,
    *,
    ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load dimension definition files keyed by dimension id.

    Only loads files for the requested ids (or all known ids when ids=None).
    """
    targets = ids if ids is not None else list(_DIMENSION_DEF_FILES.keys())
    result: dict[str, dict[str, Any]] = {}
    for dim_id in targets:
        filename = _DIMENSION_DEF_FILES.get(dim_id)
        if filename is None:
            raise KeyError(f"unknown dimension id: {dim_id!r}")
        path = dimension_defs_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing dimension def: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"dimension def must be an object: {path}")
        result[dim_id] = data
    return result


def select_dimension_defs(
    *,
    cycle_type: str,
    dimension_defs_dir: Path,
    mode: str = "tech",
    upstream_baseline_ref: str = "",
) -> list[dict[str, Any]]:
    """Return ordered dimension definitions for compose_corpus.

    Passes mode and upstream_baseline_ref to select_dimension_ids to determine whether
    intent-alignment (d3) is included.
    """
    require_feature_eval(cycle_type)
    ids = select_dimension_ids(mode=mode, upstream_baseline_ref=upstream_baseline_ref)
    defs = load_dimension_defs(dimension_defs_dir, ids=ids)
    return [copy.deepcopy(defs[dim_id]) for dim_id in ids]
