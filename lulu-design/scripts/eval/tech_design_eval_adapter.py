#!/usr/bin/env python3
"""lulu-design implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import subprocess
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

_WORKFLOW_ID = "lulu-design"

from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    load_container_meta,
)
from workflow_profile_paths import (  # noqa: E402
    doc_dir,
    document_path,
    eval_round_dir,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402

sys.path.insert(0, str(EVAL_SCRIPTS))
from workflow_adapter import SessionContext  # noqa: E402

from tech_design_eval_policy import select_dimension_defs  # noqa: E402

_VALID_EXECUTION_MODES = frozenset({"guided", "autonomous"})

TECH_DESIGN_COMPOSED_CORPUS_ID = "lulu-design-composed"
TECH_DESIGN_COMPOSED_CORPUS_VERSION = "1"
TECH_DESIGN_COMPOSED_CORPUS_REF = (
    f"{TECH_DESIGN_COMPOSED_CORPUS_ID}@{TECH_DESIGN_COMPOSED_CORPUS_VERSION}"
)


class TechDesignEvalAdapter:
    """WorkflowAdapter for lulu-design cache layout and state machine."""

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return resolve_workflow_state_path_from_cycle(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )

    def load_workflow_state(
        self, cycle_id: str, project_root: Path
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
        self, cycle_id: str, project_root: Path
    ) -> Path:
        active_doc = load_active_doc_from_cycle(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )
        return project_root / doc_dir(cycle_id, active_doc, _WORKFLOW_ID, project_root) / "evaluate-state.md"

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        return SessionContext(
            active_doc=load_active_doc_from_cycle(
                cycle_id,
                project_root,
                profile_id=_WORKFLOW_ID,
            ),
            mode=state["mode"],
            upstream_baseline_ref=frozen_delivered_path_by_type(revision_dir, "lulu-spec"),
            cycle_type=detect_cycle_type(cycle_id),
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
        return {
            "compose_doc": compose_doc,
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root / eval_round_dir(
                    cycle_id,
                    active_doc,
                    evaluate_round,
                    _WORKFLOW_ID,
                    project_root,
                )
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: ['product', 'tech'])",
            )
        return TECH_DESIGN_COMPOSED_CORPUS_REF

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        from corpus_compose import compose_corpus  # noqa: WPS433

        cycle_type = detect_cycle_type(cycle_id)
        state = self.load_workflow_state(cycle_id, project_root)
        mode = state.get("mode", "tech")
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        upstream_baseline_ref = frozen_delivered_path_by_type(revision_dir, "lulu-spec")
        dimensions = select_dimension_defs(
            cycle_type=cycle_type,
            dimension_defs_dir=self.dimension_defs_dir(),
            mode=mode,
            upstream_baseline_ref=upstream_baseline_ref,
        )
        return compose_corpus(
            corpus_id=TECH_DESIGN_COMPOSED_CORPUS_ID,
            corpus_version=TECH_DESIGN_COMPOSED_CORPUS_VERSION,
            scope="lulu-design",
            dimensions=dimensions,
            review_output_prefix="design-review",
        )

    def dimension_defs_dir(self) -> Path:
        return shell_path(load_profile(_WORKFLOW_ID), "dimension_defs_dir")

    @staticmethod
    def _empty_corpus_bind() -> dict[str, str]:
        return {
            "tdt_design_quality_framework_url": "",
            "tdt_product_tech_spec_crosscheck_url": "",
        }

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        from subagent_config import detect_platform, get_stage_config_bucket  # noqa: WPS433

        plat = detect_platform(None)
        section = get_stage_config_bucket(project_root.resolve(), "lulu-design", "eval", plat)
        if not section:
            return self._empty_corpus_bind()
        framework_url = str(
            section.get("tdt_design_quality_framework_url", ""),
        ).strip()
        crosscheck_url = str(
            section.get("tdt_product_tech_spec_crosscheck_url", ""),
        ).strip()
        return {
            "tdt_design_quality_framework_url": framework_url,
            "tdt_product_tech_spec_crosscheck_url": crosscheck_url,
        }

    def detect_cycle_type(self, cycle_id: str) -> str:
        return detect_cycle_type(cycle_id)

    def resolve_execution_mode(
        self, cycle_id: str, project_root: Path
    ) -> str:
        cycle_type = detect_cycle_type(cycle_id)
        cache_dir = project_root.resolve() / CACHE_DIR
        try:
            meta = load_container_meta(cache_dir, cycle_id, cycle_type)
        except ValueError:
            return "guided"
        if not meta:
            return "guided"
        mode = meta.get("execution_mode", "guided")
        if mode not in _VALID_EXECUTION_MODES:
            return "guided"
        return mode

    def enter_evaluating(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        from evaluate_state_ops import init_evaluate_state_for_session  # noqa: WPS433
        from session_evaluating import enter_evaluating_state  # noqa: WPS433

        result = enter_evaluating_state(
            cycle_id,
            project_root,
            profile_id=_WORKFLOW_ID,
        )
        if not result.get("ok"):
            return result
        if result.get("transitioned"):
            init_evaluate_state_for_session(self, cycle_id, project_root)
        return result
