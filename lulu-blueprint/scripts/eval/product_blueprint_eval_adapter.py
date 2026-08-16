#!/usr/bin/env python3
"""lulu-blueprint implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_EVAL_SHELL = Path(__file__).resolve().parent
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
for p in (_KERNEL_SCRIPTS, _EVAL_SHELL, _EVAL_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import EVAL_SCRIPTS, load_profile, shell_path  # noqa: E402

_WORKFLOW_ID = "lulu-blueprint"
LULU_BLUEPRINT_COMPOSED_CORPUS_ID = "lulu-blueprint-composed"
LULU_BLUEPRINT_COMPOSED_CORPUS_VERSION = "2"
LULU_BLUEPRINT_COMPOSED_CORPUS_REF = (
    f"{LULU_BLUEPRINT_COMPOSED_CORPUS_ID}@{LULU_BLUEPRINT_COMPOSED_CORPUS_VERSION}"
)

from l_ledger_schema import eval_session_phase, load_l_ledger  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    document_path,
    eval_layout_for_revision,
    eval_round_dir_for_layout,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)

from eval_handoff_control import resolve_evaluate_state_abs  # noqa: E402
from compose_eval_adapter_support import ComposeEvalAdapterSupport  # noqa: E402
from l_step_control import (  # noqa: E402
    enter_evaluating_state,
    rollback_evaluating_phase,
)
sys.path.insert(0, str(EVAL_SCRIPTS))
from workflow_adapter import SessionContext  # noqa: E402
from evaluate_state_ops import init_evaluate_state_for_corpus  # noqa: E402
from corpus_compose import compose_corpus  # noqa: E402

from product_blueprint_eval_policy import select_dimension_defs  # noqa: E402

class ProductBlueprintEvalAdapter(ComposeEvalAdapterSupport):
    """WorkflowAdapter for lulu-blueprint cache layout and state machine."""

    WORKFLOW_ID = _WORKFLOW_ID

    def resolve_workflow_state_path(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> Path:
        return resolve_workflow_state_path_from_cycle(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )

    def load_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> dict[str, str]:
        ws_path = self.resolve_workflow_state_path(cycle_id, project_root)
        return load_workflow_state(ws_path)

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None:
        ws_path = self.resolve_workflow_state_path(cycle_id, project_root)
        save_workflow_state(ws_path, updates, merge=merge)

    def resolve_evaluate_state_path(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> Path:
        return resolve_evaluate_state_abs(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )

    def session_context(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        try:
            phase = eval_session_phase(revision_dir)
        except (FileNotFoundError, ValueError, OSError):
            phase = "pending"
        return SessionContext(
            active_doc=load_active_doc_from_cycle(
                cycle_id,
                project_root,
                profile_id=_WORKFLOW_ID,
            ),
            mode=state["mode"],
            upstream_baseline_ref="",
            cycle_type=detect_cycle_type(cycle_id),
            focus_phase=phase,
        )

    def eval_paths(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        active_doc: int,
        evaluate_round: int,
        es_path: Path,
    ) -> dict[str, str]:
        root = project_root.resolve()
        compose_doc = (
            root / document_path(cycle_id, active_doc, _WORKFLOW_ID, project_root)
        ).as_posix()
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        layout = eval_layout_for_revision(revision_dir)
        focus_l = "L1"
        try:
            focus_l = str(load_l_ledger(revision_dir)["focus"])
        except (FileNotFoundError, ValueError, OSError, KeyError):
            pass
        return {
            "compose_doc": compose_doc,
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root
                / eval_round_dir_for_layout(
                    cycle_id,
                    active_doc,
                    evaluate_round,
                    _WORKFLOW_ID,
                    project_root,
                    layout=layout,
                    focus_l=focus_l,
                )
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: ['product', 'tech'])",
            )
        return LULU_BLUEPRINT_COMPOSED_CORPUS_REF

    def resolve_eval_corpus(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> dict[str, Any]:
        cycle_type = detect_cycle_type(cycle_id)
        dimensions = select_dimension_defs(
            cycle_type=cycle_type,
            dimension_defs_dir=self.dimension_defs_dir(),
        )
        return compose_corpus(
            corpus_id=LULU_BLUEPRINT_COMPOSED_CORPUS_ID,
            corpus_version=LULU_BLUEPRINT_COMPOSED_CORPUS_VERSION,
            scope="lulu-blueprint",
            dimensions=dimensions,
            review_output_prefix="blueprint-review",
        )

    def dimension_defs_dir(self) -> Path:
        return shell_path(load_profile(_WORKFLOW_ID), "dimension_defs_dir")

    def detect_cycle_type(self, cycle_id: str) -> str:
        return detect_cycle_type(cycle_id)

    def enter_evaluating(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> dict[str, Any]:
        result = enter_evaluating_state(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )
        if not result.get("ok"):
            return result
        if result.get("transitioned"):
            focus = str(result.get("focus") or "")
            try:
                init_evaluate_state_for_corpus(
                    self.resolve_evaluate_state_path(cycle_id, project_root),
                    self.resolve_eval_corpus(cycle_id, project_root),
                    eval_capability=self.EVAL_CAPABILITY,
                    cycle_type=self.detect_cycle_type(cycle_id),
                    evaluate_round=int(result.get("evaluate_round") or 1),
                    focus_l=focus,
                )
            except Exception as exc:
                revision_dir = self.resolve_workflow_state_path(
                    cycle_id, project_root
                ).parent
                if focus:
                    rollback_evaluating_phase(revision_dir, focus=focus)
                return {
                    "ok": False,
                    "current_state": result.get("current_state", "Working"),
                    "transitioned": False,
                    "error": str(exc),
                    "resume": {
                        "entry": "Working",
                        "action": f"evaluate-state init failed; phase rolled back: {exc}",
                    },
                }
        return result
