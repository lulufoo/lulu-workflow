#!/usr/bin/env python3
"""Inclusion policy for tech-plan dynamic EvalCorpus composition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_STAMP_FILES = {
    "intent-alignment": "intent-alignment.json",
    "codebase-consistency": "codebase-consistency.json",
    "solution-quality": "solution-quality.json",
}

_INTENT_EVAL_CONFIG_KEY = "tpt_intent_eval_framework_url"

_TOPIC_EVAL_NOT_IMPLEMENTED = (
    "topic eval stamps are not implemented yet; "
    "only feature cycles can enter Evaluating."
)


def select_dimension_ids(*, product_ref: str, mode: str) -> list[str]:
    """Return ordered dimension ids for this session."""
    if mode == "product" and not product_ref.strip():
        raise ValueError(
            "mode is 'product' but product_ref is empty; "
            "provide product_ref or use mode 'tech'."
        )
    ids = ["codebase-consistency", "solution-quality"]
    if product_ref.strip():
        ids.insert(0, "intent-alignment")
    return ids


def intent_eval_config_key(cycle_type: str) -> str:
    """Return workflow-config key for intent-eval framework URL."""
    return _INTENT_EVAL_CONFIG_KEY


def stamps_dir_for_cycle_type(corpora_dir: Path, cycle_type: str) -> Path:
    """Return stamp directory for cycle_type; topic is reserved but not implemented."""
    if cycle_type == "feature":
        return corpora_dir / "stamps" / "feature"
    if cycle_type == "topic":
        raise ValueError(_TOPIC_EVAL_NOT_IMPLEMENTED)
    raise ValueError(f"unsupported cycle_type for eval: {cycle_type!r}")


def load_stamps(stamps_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all dimension stamps keyed by dimension id."""
    result: dict[str, dict[str, Any]] = {}
    for dim_id, filename in _STAMP_FILES.items():
        path = stamps_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing dimension stamp: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"stamp must be an object: {path}")
        result[dim_id] = data
    return result


def select_dimension_defs(
    *,
    product_ref: str,
    mode: str,
    cycle_type: str,
    corpora_dir: Path,
) -> list[dict[str, Any]]:
    """Return ordered dimension definitions for compose_corpus."""
    stamps_dir = stamps_dir_for_cycle_type(corpora_dir, cycle_type)
    stamps = load_stamps(stamps_dir)
    ids = select_dimension_ids(product_ref=product_ref, mode=mode)
    return [copy.deepcopy(stamps[dim_id]) for dim_id in ids]
