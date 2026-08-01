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
from scope_package_projection import (  # noqa: E402
    is_decision_package_ref,
    load_decision_package,
    reject_decision_package_as_scope,
    write_scope_package_projection,
)
from start_adapter import primary_scope_from_workflow  # noqa: E402
from start_scope_helpers import first_ref  # noqa: E402


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
            has_approach = entry_path_ok(data, "lulu-approach")
            if not has_design and not has_approach:
                errors.append(
                    "missing delivered-refs entry: lulu-design or lulu-approach",
                )
            elif not has_design:
                approach = ref_from_file_entry("lulu-approach", data)
                if approach is None or not is_decision_package_ref(approach):
                    errors.append(
                        "lulu-approach must deliver decision-package.json "
                        "(artifact=decision-package); legacy whole decision-fact "
                        "scope is retired (archive-2.0)"
                    )
                else:
                    try:
                        load_decision_package(Path(approach.path))
                    except (OSError, ValueError) as exc:
                        errors.append(f"invalid decision-package: {exc}")
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
        revision_dir: Path | None = None,
    ) -> list[DeliveredRef]:
        """Primary scope: design package, or approach decision-package projection.

        When primary is ``lulu-design``, path is ``*-package.json`` (delivery
        marker). When primary is ``lulu-approach``, require ``decision-package``
        and project to revision ``scope-package.json`` (archive-2.0). Legacy whole
        ``decision-fact`` as ``$SCOPE_REF`` is retired.
        """
        del run_mode, carry_forward_ref
        primary = first_ref(delivered_refs, "lulu-design") or first_ref(
            delivered_refs,
            "lulu-approach",
        )
        if primary is None:
            return []
        if primary.type == "lulu-design":
            return [primary]
        if not is_decision_package_ref(primary):
            raise ValueError(
                "lulu-approach scope requires decision-package.json "
                "(artifact=decision-package); legacy whole decision-fact Path A "
                "is retired — re-deliver approach via deliver"
            )
        if revision_dir is None:
            raise ValueError(
                "revision_dir required to project decision-package → scope-package"
            )
        scope_path = write_scope_package_projection(
            decision_package_path=Path(primary.path),
            revision_dir=Path(revision_dir),
        )
        reject_decision_package_as_scope(scope_path)
        return [
            DeliveredRef(
                type=primary.type,
                path=str(scope_path.resolve()),
                artifact="scope-package",
            )
        ]

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
        delivered_refs: list[DeliveredRef] | None = None,
    ) -> list[DeliveredRef]:
        del cycle_id, project_root, delivered_refs
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
