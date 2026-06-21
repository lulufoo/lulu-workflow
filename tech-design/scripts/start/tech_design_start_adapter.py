#!/usr/bin/env python3
"""tech-design StartAdapter implementation."""

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
    load_delivered_refs_file,
    ref_from_file_entry,
)
from start_adapter import primary_scope_from_workflow  # noqa: E402
from start_scope_helpers import first_ref  # noqa: E402


class TechDesignStartAdapter:
    """Start rules for tech-design compose profile."""

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        del run_mode, carry_forward_ref
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "tech-diagnostic"):
            return ["missing delivered-refs entry: tech-diagnostic"]
        return []

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        del run_mode
        data = load_delivered_refs_file(cycle_id, project_root)
        ref = ref_from_file_entry("tech-diagnostic", data)
        if ref is None or not Path(ref.path).is_file():
            return []
        return [ref]

    def resolve_scope_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
        carry_forward_ref: str = "",
    ) -> list[DeliveredRef]:
        del run_mode, carry_forward_ref
        primary = first_ref(delivered_refs, "tech-diagnostic")
        return [primary] if primary is not None else []

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        return primary_scope_from_workflow(cycle_id, project_root, "tech-design")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del run_mode, carry_forward_ref, scope_refs
        return (
            "设计阶段：Initializing 完成后暂停；可选 Evaluating（d1 代码库一致性 + "
            "d2 方案质量）或 Deliver。"
        )
