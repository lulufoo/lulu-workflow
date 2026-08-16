#!/usr/bin/env python3
"""lulu-blueprint StageEvalContributor — Dimension selection only."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_EVAL_SHELL = Path(__file__).resolve().parent
for path in (_KERNEL_SCRIPTS, _EVAL_SHELL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from product_blueprint_eval_policy import select_dimension_defs  # noqa: E402
from stage_eval_contributor import ComposeEvalContext, StageEvalContribution  # noqa: E402


class ProductBlueprintEvalContributor:
    """Select lulu-blueprint Dimensions; do not own handoff or corpus identity."""

    def contribute(self, *, context: ComposeEvalContext) -> StageEvalContribution:
        return StageEvalContribution(
            dimensions=select_dimension_defs(
                cycle_type=context.cycle_type,
                dimension_defs_dir=context.dimension_defs_dir,
            ),
            bindings={},
            review_output_prefix="blueprint-review",
        )
