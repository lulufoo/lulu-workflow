#!/usr/bin/env python3
"""lulu-plan StageEvalContributor — Dimension selection only."""

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
from compose_package_schema import (  # noqa: E402
    is_compose_package_path,
    load_compose_package,
    resolve_focus_doc_path,
)
from l_ledger_schema import load_l_ledger  # noqa: E402
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402
from stage_eval_contributor import ComposeEvalContext, StageEvalContribution  # noqa: E402
from tech_plan_eval_policy import select_dimension_defs  # noqa: E402


class TechPlanEvalContributor:
    """Select lulu-plan Dimensions; do not own handoff or corpus identity."""

    def contribute(self, *, context: ComposeEvalContext) -> StageEvalContribution:
        tech_design_ref = frozen_delivered_path_by_type(context.revision_dir, "lulu-design")
        tech_diagnostic_ref = frozen_delivered_path_by_type(
            context.revision_dir, "lulu-approach"
        )
        bindings = {}
        upstream_doc_path = _resolve_upstream_doc_path(
            context.revision_dir,
            tech_design_path=tech_design_ref,
            tech_diagnostic_path=tech_diagnostic_ref,
        )
        if upstream_doc_path.strip():
            bindings["upstream_doc_path"] = upstream_doc_path
        return StageEvalContribution(
            dimensions=select_dimension_defs(
                cycle_type=context.cycle_type,
                dimension_defs_dir=context.dimension_defs_dir,
                tech_design_ref=tech_design_ref,
                tech_diagnostic_ref=tech_diagnostic_ref,
            ),
            bindings=bindings,
            review_output_prefix="tech-review",
            upstream_baseline_ref=frozen_delivered_path_by_type(
                context.revision_dir, "lulu-spec"
            ),
        )


def _resolve_upstream_doc_path(
    revision_dir: Path,
    *,
    tech_design_path: str,
    tech_diagnostic_path: str,
) -> str:
    if tech_design_path and is_compose_package_path(tech_design_path):
        package_path = Path(tech_design_path)
        try:
            package = load_compose_package(package_path)
            focus = str(load_l_ledger(revision_dir).get("focus", "")).strip()
            if not focus:
                return ""
            return str(resolve_focus_doc_path(package, focus, package_path=package_path))
        except (FileNotFoundError, ValueError):
            return tech_design_path or tech_diagnostic_path
    return tech_design_path or tech_diagnostic_path
