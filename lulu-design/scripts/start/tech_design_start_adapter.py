#!/usr/bin/env python3
"""lulu-design StartAdapter implementation."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
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
    """Start rules for lulu-design compose profile."""

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
        if not entry_path_ok(data, "lulu-approach"):
            errors.append("missing delivered-refs entry: lulu-approach")
        if run_mode == "product" and not entry_path_ok(data, "lulu-spec"):
            errors.append("missing delivered-refs entry: lulu-spec")
        return errors

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        data = load_delivered_refs_file(cycle_id, project_root)
        types = ["lulu-approach"]
        if run_mode == "product":
            types.append("lulu-spec")
        refs: list[DeliveredRef] = []
        for dtype in types:
            ref = ref_from_file_entry(dtype, data)
            if ref is not None and Path(ref.path).is_file():
                refs.append(ref)
        return refs

    def resolve_scope_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
        carry_forward_ref: str = "",
    ) -> list[DeliveredRef]:
        del carry_forward_ref
        primary = first_ref(delivered_refs, "lulu-approach")
        out = [primary] if primary is not None else []
        if run_mode == "product":
            product = first_ref(delivered_refs, "lulu-spec")
            if product is not None:
                out.append(product)
        return out

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        return primary_scope_from_workflow(cycle_id, project_root, "lulu-design")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del carry_forward_ref, scope_refs
        if run_mode == "product":
            return (
                "设计阶段（产品模式）：Inductive → Initializing 完成后暂停；可选 FreeEdit、"
                "Evaluating（d1 代码库一致性 + d2 方案质量 + d3 产品意图对齐）或 Deliver。"
            )
        return (
            "设计阶段：Inductive → Initializing 完成后暂停；可选 FreeEdit、"
            "Evaluating（d1 代码库一致性 + d2 方案质量）或 Deliver。"
        )
