#!/usr/bin/env python3
"""lulu-design StageEvalContributor — Dimension selection only."""

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
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402
from stage_eval_contributor import ComposeEvalContext, StageEvalContribution  # noqa: E402
from tech_design_eval_policy import select_dimension_defs  # noqa: E402


class TechDesignEvalContributor:
    """Select lulu-design Dimensions; do not own handoff or corpus identity."""

    def contribute(self, *, context: ComposeEvalContext) -> StageEvalContribution:
        upstream = frozen_delivered_path_by_type(context.revision_dir, "lulu-spec")
        return StageEvalContribution(
            dimensions=select_dimension_defs(
                cycle_type=context.cycle_type,
                dimension_defs_dir=context.dimension_defs_dir,
                mode=context.mode,
                upstream_baseline_ref=upstream,
            ),
            bindings={},
            review_output_prefix="design-review",
            upstream_baseline_ref=upstream,
        )
