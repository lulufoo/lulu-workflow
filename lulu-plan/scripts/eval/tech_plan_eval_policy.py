#!/usr/bin/env python3
"""Inclusion policy for lulu-plan dynamic EvalCorpus composition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_DIMENSION_DEF_FILES = {
    "codebase-consistency": "codebase-consistency.json",
    "solution-quality": "solution-quality.json",
}

_TOPIC_EVAL_BLOCKED = (
    "topic cycles do not evaluate in lulu-plan; "
    "use lulu-arch stage for topic Evaluating."
)


def select_dimension_ids() -> list[str]:
    """Return ordered dimension ids for this session.

    Dispatch rules:
    - codebase-consistency + solution-quality: always
    """
    return ["codebase-consistency", "solution-quality"]


def require_feature_eval(cycle_type: str) -> None:
    """Raise when cycle_type cannot use lulu-plan Evaluating."""
    if cycle_type == "topic":
        raise ValueError(_TOPIC_EVAL_BLOCKED)
    if cycle_type != "feature":
        raise ValueError(f"unsupported cycle_type for eval: {cycle_type!r}")


def load_dimension_defs(dimension_defs_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all dimension definition files keyed by dimension id."""
    result: dict[str, dict[str, Any]] = {}
    for dim_id, filename in _DIMENSION_DEF_FILES.items():
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
) -> list[dict[str, Any]]:
    """Return ordered dimension definitions for compose_corpus."""
    require_feature_eval(cycle_type)
    defs = load_dimension_defs(dimension_defs_dir)
    return [copy.deepcopy(defs[dim_id]) for dim_id in select_dimension_ids()]
