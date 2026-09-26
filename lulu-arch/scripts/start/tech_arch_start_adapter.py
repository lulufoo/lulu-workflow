#!/usr/bin/env python3
"""lulu-arch StartAdapter implementation."""

from __future__ import annotations

import json
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
    reject_non_scope_package,
    write_scope_package_from_source,
)
from start_scope_helpers import first_ref  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402

_DECISION_PACKAGE_FILENAME = "decision-package.json"
_DECISION_PACKAGE_ARTIFACT = "decision-package"


def _is_decision_package_ref(ref: DeliveredRef) -> bool:
    if str(ref.artifact or "").strip() == _DECISION_PACKAGE_ARTIFACT:
        return True
    return Path(ref.path).name == _DECISION_PACKAGE_FILENAME


def _decision_doc_from_package(package_path: Path) -> Path:
    """Upstream contract: ``main.decision_doc_path`` relative to the package dir."""
    path = Path(package_path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    main = data.get("main") if isinstance(data, dict) else None
    rel = str((main or {}).get("decision_doc_path", "")).strip()
    if not rel:
        raise ValueError("decision-package.main.decision_doc_path is required")
    doc = (path.parent / rel).resolve()
    if not doc.is_file():
        raise ValueError(f"decision doc not found: {doc}")
    return doc


class TechArchStartAdapter:
    """Start rules for lulu-arch compose profile (topic cycles only)."""

    def infer_run_mode(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> str:
        del cycle_id, project_root
        return "tech"

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[str]:
        if run_mode not in ("tech",):
            return [f"invalid run_mode: {run_mode!r} (lulu-arch is tech-only)"]
        if detect_cycle_type(cycle_id) != "topic":
            return ["lulu-arch is topic-only; feature cycles are not supported"]
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "lulu-approach"):
            return ["missing delivered-refs entry: lulu-approach"]
        ref = ref_from_file_entry("lulu-approach", data)
        if ref is None or not _is_decision_package_ref(ref):
            return [
                "lulu-approach must deliver a decision-package.json "
                "(artifact=decision-package)"
            ]
        try:
            _decision_doc_from_package(Path(ref.path))
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
        ref = ref_from_file_entry("lulu-approach", data)
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
        """Project lulu-approach's decision doc to a scope-package."""
        del run_mode
        dest = output_dir or revision_dir
        primary = first_ref(delivered_refs, "lulu-approach")
        if primary is None:
            return []
        if not _is_decision_package_ref(primary):
            raise ValueError(
                "lulu-approach scope requires a decision-package.json "
                "(artifact=decision-package)"
            )
        if dest is None:
            raise ValueError("output_dir required to project → scope-package")
        scope_path = write_scope_package_from_source(
            source_path=_decision_doc_from_package(Path(primary.path)),
            output_dir=Path(dest),
            overwrite=True,
        )
        reject_non_scope_package(scope_path)
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
        return primary_scope_from_workflow(cycle_id, project_root, "lulu-arch")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del run_mode, scope_refs
        return (
            "Topic technical architecture stage: pause after Writing; "
            "then choose FreeEdit, Evaluating (arch-quality), or Deliver."
        )
