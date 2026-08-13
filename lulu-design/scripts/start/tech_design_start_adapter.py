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
from workflow_common import CACHE_DIR  # noqa: E402

_WORKFLOW_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))
from start_gate import get_topic_ref  # noqa: E402

from scope_package_projection import (  # noqa: E402
    is_decision_package_ref,
    load_decision_package,
    make_norm_ref,
    norm_refs_from_decision_package,
    reject_decision_package_as_scope,
    write_scope_package_projection,
)


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
    ) -> list[str]:
        errors: list[str] = []
        if run_mode not in ("product", "tech"):
            errors.append(f"invalid run_mode: {run_mode!r}")
            return errors
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "lulu-approach"):
            errors.append("missing delivered-refs entry: lulu-approach")
        else:
            approach = ref_from_file_entry("lulu-approach", data)
            if approach is None:
                errors.append("missing delivered-refs entry: lulu-approach")
            elif not is_decision_package_ref(approach):
                errors.append(
                    "lulu-approach must deliver a decision-package.json "
                    "(artifact=decision-package)"
                )
            else:
                try:
                    load_decision_package(Path(approach.path))
                except (OSError, ValueError) as exc:
                    errors.append(f"invalid decision-package: {exc}")
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
        revision_dir: Path | None = None,
    ) -> list[DeliveredRef]:
        """Primary scope SSOT for design start.

        Requires ``artifact=decision-package`` (or path ``decision-package.json``);
        projects to revision ``scope-package.json`` (``revision_dir``; D3 write-once).
        """
        del run_mode
        primary = first_ref(delivered_refs, "lulu-approach")
        if primary is None:
            return []
        if not is_decision_package_ref(primary):
            raise ValueError(
                "lulu-approach scope requires a decision-package.json "
                "(artifact=decision-package)"
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
        if run_mode != "product":
            return []
        spec = first_ref(delivered_refs, "lulu-spec")
        return [spec] if spec is not None else []

    def resolve_norm_constraint_refs(
        self,
        *,
        cycle_id: str,
        project_root: Path | None = None,
        delivered_refs: list[DeliveredRef] | None = None,
    ) -> list[DeliveredRef]:
        refs: list[DeliveredRef] = []
        approach: DeliveredRef | None = None
        if delivered_refs is not None:
            approach = first_ref(delivered_refs, "lulu-approach")
        elif project_root is not None:
            data = load_delivered_refs_file(cycle_id, project_root)
            approach = ref_from_file_entry("lulu-approach", data)

        if approach is not None and is_decision_package_ref(approach):
            refs.extend(
                norm_refs_from_decision_package(
                    decision_package_path=Path(approach.path),
                )
            )

        if project_root is not None:
            topic = get_topic_ref(cycle_id, "lulu-design", project_root / CACHE_DIR)
            if topic is not None:
                refs.append(
                    make_norm_ref(
                        delivered_type=str(topic["type"]),
                        path=str(topic["path"]),
                        kind="topic_arch",
                    )
                )
        return refs

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
        scope_refs: list[DeliveredRef],
    ) -> str:
        del scope_refs
        if run_mode == "product":
            return (
                "设计阶段（产品模式）：Inductive → Writing 完成后暂停；可选 FreeEdit、"
                "Evaluating（d1 代码库一致性 + d2 方案质量 + d3 产品意图对齐）或 Deliver。"
            )
        return (
            "设计阶段：Inductive → Writing 完成后暂停；可选 FreeEdit、"
            "Evaluating（d1 代码库一致性 + d2 方案质量）或 Deliver。"
        )
