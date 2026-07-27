#!/usr/bin/env python3
"""lulu-plan StartAdapter implementation."""

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


class TechPlanStartAdapter:
    """Start rules for lulu-plan compose profile."""

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
        if run_mode == "product":
            if not entry_path_ok(data, "lulu-spec"):
                errors.append("missing delivered-refs entry: lulu-spec")
        else:
            has_design = entry_path_ok(data, "lulu-design")
            has_diag = entry_path_ok(data, "lulu-approach")
            if not has_design and not has_diag:
                errors.append(
                    "missing delivered-refs entry: lulu-design or lulu-approach",
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
            types = ["lulu-spec", "lulu-design"]
        elif entry_path_ok(data, "lulu-design"):
            types = ["lulu-design"]
        else:
            types = ["lulu-approach"]
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
        """Primary scope: design-doc, or approach decision-fact when falling back.

        When primary is ``lulu-design``, path stays the design prose doc (delivery
        SSOT = document; Atomize at Deductive Intake). When primary is
        ``lulu-approach``, ``decision_fact_path`` with units is required (no prose
        fallback).
        """
        del run_mode, carry_forward_ref
        primary = first_ref(delivered_refs, "lulu-design") or first_ref(
            delivered_refs,
            "lulu-approach",
        )
        if primary is None:
            return []
        if primary.type == "lulu-approach":
            return [require_decision_fact_scope(primary)]
        return [primary]

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
        del cycle_id, project_root
        return []

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        return primary_scope_from_workflow(cycle_id, project_root, "lulu-plan")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del scope_refs
        if run_mode == "product":
            if carry_forward_ref:
                return (
                    "⚠️  carry_forward_ref 存在，进入 Drafting 后必须强制校准"
                    "（对比新 product-doc 与旧 tech-doc）。"
                )
            return (
                "首次起草（产品需求模式），进入 Drafting 后必须校准"
                "（读取模板 + 架构约束 + product-doc）。"
            )
        return (
            "技改模式：执行 E2（代码库一致性）+ E3（方案质量 / TPEF）"
            " + E4（tech-conformance，对照上游 design-doc 或 decision-doc）。"
        )
