#!/usr/bin/env python3
"""Narrow Stage port that contributes Dimensions; Compose owns WorkflowAdapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_REVIEW_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COMMON_DIMENSION_IDS = frozenset(
    {"intent-fidelity", "parent-continuity", "norm-conformance"}
)


@dataclass(frozen=True)
class ComposeEvalContext:
    """Facts a Stage contributor may use to select Dimensions and bindings."""

    cycle_id: str
    project_root: Path
    workflow_id: str
    revision_dir: Path
    cycle_type: str
    mode: str
    dimension_defs_dir: Path
    focus_l: str


@dataclass(frozen=True)
class StageEvalContribution:
    """Stage-owned Dimension set for one Compose Eval corpus compose."""

    dimensions: list[dict[str, Any]]
    bindings: dict[str, str]
    review_output_prefix: str
    upstream_baseline_ref: str = ""


class StageEvalContributor(Protocol):
    def contribute(self, *, context: ComposeEvalContext) -> StageEvalContribution: ...


def validate_contribution(contribution: Any) -> StageEvalContribution:
    """Fail-closed before any Evaluating phase mutation."""
    if not isinstance(contribution, StageEvalContribution):
        raise ValueError("contributor.contribute must return StageEvalContribution")
    if not isinstance(contribution.dimensions, list) or not contribution.dimensions:
        raise ValueError("contribution.dimensions must be a non-empty list")
    for index, dimension in enumerate(contribution.dimensions):
        if not isinstance(dimension, dict):
            raise ValueError(f"contribution.dimensions[{index}] must be an object")
        dim_id = str(dimension.get("id") or "").strip()
        if not dim_id:
            raise ValueError(f"contribution.dimensions[{index}] missing id")
        alias = str(dimension.get("legacy_alias") or "").strip()
        if dim_id in _COMMON_DIMENSION_IDS or alias in _COMMON_DIMENSION_IDS:
            raise ValueError(
                f"contribution.dimensions[{index}] must not use a common dimension id"
            )
    if not isinstance(contribution.bindings, dict):
        raise ValueError("contribution.bindings must be an object")
    bindings: dict[str, str] = {}
    for key, value in contribution.bindings.items():
        name = str(key).strip()
        if not name:
            raise ValueError("contribution.bindings keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"contribution.bindings[{name!r}] must be a non-empty string"
            )
        bindings[name] = value
    prefix = str(contribution.review_output_prefix or "").strip()
    if not _REVIEW_PREFIX.match(prefix):
        raise ValueError("contribution.review_output_prefix must be a safe filename prefix")
    return StageEvalContribution(
        dimensions=list(contribution.dimensions),
        bindings=bindings,
        review_output_prefix=prefix,
        upstream_baseline_ref=str(contribution.upstream_baseline_ref or ""),
    )
