#!/usr/bin/env python3
"""tech-plan StartAdapter implementation."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    entry_path_ok,
    init_scope_ref_from_state,
    load_delivered_refs_file,
    ref_from_file_entry,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)


class TechPlanStartAdapter:
    """Start rules for tech-plan compose profile."""

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        del carry_forward_ref
        errors: list[str] = []
        if run_mode not in ("product", "tech"):
            errors.append(f"invalid run_mode: {run_mode!r}")
            return errors
        data = load_delivered_refs_file(cycle_id, project_root)
        if run_mode == "product":
            if not entry_path_ok(data, "product-plan"):
                errors.append("missing delivered-refs entry: product-plan")
        else:
            has_design = entry_path_ok(data, "tech-design")
            has_diag = entry_path_ok(data, "tech-diagnostic")
            if not has_design and not has_diag:
                errors.append(
                    "missing delivered-refs entry: tech-design or tech-diagnostic",
                )
        return errors

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        data = load_delivered_refs_file(cycle_id, project_root)
        if run_mode == "product":
            types = ["product-plan", "tech-design"]
        elif entry_path_ok(data, "tech-design"):
            types = ["tech-design"]
        else:
            types = ["tech-diagnostic"]
        refs: list[DeliveredRef] = []
        for dtype in types:
            ref = ref_from_file_entry(dtype, data)
            if ref is not None and Path(ref.path).is_file():
                refs.append(ref)
        return refs

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        return init_scope_ref_from_state(load_workflow_state(ws_path), "tech-plan")
