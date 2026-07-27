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
from start_scope_helpers import (  # noqa: E402
    first_ref,
    require_decision_fact_scope,
)
from workflow_common import CACHE_DIR  # noqa: E402

_WORKFLOW_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))
from start_gate import get_topic_ref  # noqa: E402


class TechDesignStartAdapter:
    """Start rules for lulu-design compose profile."""

    def infer_run_mode(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> str:
        data = load_delivered_refs_file(cycle_id, project_root)
        if entry_path_ok(data, "lulu-spec"):
            return "product"
        return "tech"

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
        """Primary scope SSOT = ``decision_fact_path`` (must have units).

        ``DeliveredRef.path`` on the returned scope ref is what compose dispatches as
        ``$SCOPE_REF``. Cycle ``entry.path`` (decision-doc.md) stays on the approach
        entry for human/eval — not compose scope.
        """
        del run_mode, carry_forward_ref
        primary = first_ref(delivered_refs, "lulu-approach")
        if primary is None:
            return []
        return [require_decision_fact_scope(primary)]

    def resolve_intent_baseline_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
    ) -> list[DeliveredRef]:
        if run_mode != "product":
            return []
        spec = first_ref(delivered_refs, "lulu-spec")
        return [spec] if spec is not None else []

    def resolve_norm_constraint_refs(
        self,
        *,
        cycle_id: str,
        project_root: Path | None = None,
    ) -> list[DeliveredRef]:
        if project_root is None:
            return []
        ref = get_topic_ref(cycle_id, "lulu-design", project_root / CACHE_DIR)
        return [DeliveredRef(type=ref["type"], path=ref["path"])] if ref is not None else []

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
