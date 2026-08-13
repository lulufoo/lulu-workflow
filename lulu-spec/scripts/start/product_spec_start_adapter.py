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
from resolved_refs_schema import primary_scope_from_workflow  # noqa: E402
from scope_package_projection import (  # noqa: E402
    is_decision_package_ref,
    load_decision_package,
    reject_decision_package_as_scope,
    write_scope_package_projection,
)
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
    ) -> list[str]:
        del run_mode
        if detect_cycle_type(cycle_id) != "feature":
            return ["lulu-spec is feature-only; topic cycles are not supported"]
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "lulu-bet"):
            return ["missing delivered-refs entry: lulu-bet"]
        ref = ref_from_file_entry("lulu-bet", data)
        if ref is None or not is_decision_package_ref(ref):
            return [
                "lulu-bet must deliver a decision-package.json "
                "(artifact=decision-package)"
            ]
        try:
            load_decision_package(Path(ref.path))
        except (OSError, ValueError) as exc:
            return [f"invalid decision-package: {exc}"]
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
        output_dir: Path | None = None,
        revision_dir: Path | None = None,
    ) -> list[DeliveredRef]:
        """Project lulu-bet's decision package to a scope-package."""
        del run_mode
        dest = output_dir or revision_dir
        primary = first_ref(delivered_refs, "lulu-bet")
        if primary is None:
            return []
        if not is_decision_package_ref(primary):
            raise ValueError(
                "lulu-bet scope requires a decision-package.json "
                "(artifact=decision-package)"
            )
        if dest is None:
            raise ValueError("output_dir required to project → scope-package")
        scope_path = write_scope_package_projection(
            decision_package_path=Path(primary.path),
            output_dir=Path(dest),
            overwrite=True,
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
        del delivered_refs
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
        scope_refs: list[DeliveredRef],
    ) -> str:
        del run_mode, scope_refs
        return (
            "产品规格阶段：Drafting 从 Inductive（Step 0）开始，"
            "归纳完成后 Writing 生成 product-doc；以上游 lulu-bet scope-package 为 scope SSOT。"
        )
