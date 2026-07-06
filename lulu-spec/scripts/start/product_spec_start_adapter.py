#!/usr/bin/env python3
"""lulu-spec StartAdapter implementation."""

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
from workflow_common import CACHE_DIR, detect_cycle_type  # noqa: E402

_WORKFLOW_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))
from start_gate import get_topic_ref  # noqa: E402


class ProductSpecStartAdapter:
    """Start rules for lulu-spec compose profile (feature cycles only)."""

    def infer_run_mode(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> str:
        del cycle_id, project_root
        return "product"

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        del run_mode, carry_forward_ref
        if detect_cycle_type(cycle_id) != "feature":
            return ["lulu-spec is feature-only; topic cycles are not supported"]
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "lulu-bet"):
            return ["missing delivered-refs entry: lulu-bet"]
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
        ref = ref_from_file_entry("lulu-bet", data)
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
        primary = first_ref(delivered_refs, "lulu-bet")
        return [primary] if primary is not None else []

    def resolve_intent_baseline_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
    ) -> list[DeliveredRef]:
        del delivered_refs, run_mode
        return []

    def resolve_norm_constraint_refs(
        self,
        *,
        cycle_id: str,
        project_root: Path | None = None,
    ) -> list[DeliveredRef]:
        if project_root is None:
            return []
        ref = get_topic_ref(cycle_id, "lulu-spec", project_root / CACHE_DIR)
        return [DeliveredRef(type=ref["type"], path=ref["path"])] if ref is not None else []

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        return primary_scope_from_workflow(cycle_id, project_root, "lulu-spec")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del run_mode, carry_forward_ref, scope_refs
        return (
            "产品规格阶段：Drafting 从 Inductive（Step 0）开始，"
            "归纳完成后 Initializing 生成 product-doc；以上游 lulu-bet decision-doc 为 scope SSOT。"
        )
