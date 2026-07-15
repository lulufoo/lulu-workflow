#!/usr/bin/env python3
"""lulu-plan implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
_EVAL_SHELL = Path(__file__).resolve().parent
for p in (_KERNEL_SCRIPTS, _EVAL_SHELL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import EVAL_SCRIPTS, WORKFLOW_SCRIPTS, load_profile, shell_path  # noqa: E402

_WORKFLOW_ID = "lulu-plan"

from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    doc_dir,
    document_path,
    eval_round_dir,
)
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)

sys.path.insert(0, str(EVAL_SCRIPTS))
if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from workflow_adapter import SessionContext  # noqa: E402

from tech_plan_eval_policy import (  # noqa: E402
    intent_eval_config_key,
    select_dimension_defs,
)

LULU_PLAN_COMPOSED_CORPUS_ID = "lulu-plan-composed"
LULU_PLAN_COMPOSED_CORPUS_VERSION = "1"
LULU_PLAN_COMPOSED_CORPUS_REF = (
    f"{LULU_PLAN_COMPOSED_CORPUS_ID}@{LULU_PLAN_COMPOSED_CORPUS_VERSION}"
)


class TechPlanEvalAdapter:
    """WorkflowAdapter for lulu-plan cache layout and state machine."""

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return project_root / resolve_workflow_state_path_from_cycle(
            cycle_id,
            project_root,
            profile_id="lulu-plan",
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
        active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id="lulu-plan")

        return project_root / doc_dir(cycle_id, active_doc, _WORKFLOW_ID, project_root) / "evaluate-state.md"

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        return SessionContext(
            active_doc=load_active_doc_from_cycle(cycle_id, project_root, profile_id="lulu-plan"),
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
        return {
            "compose_doc": (
                root / document_path(cycle_id, active_doc, _WORKFLOW_ID, project_root)
            ).as_posix(),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root / eval_round_dir(cycle_id, active_doc, evaluate_round, _WORKFLOW_ID, project_root)
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: ['product', 'tech'])",
            )
        return LULU_PLAN_COMPOSED_CORPUS_REF

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        from corpus_compose import compose_corpus  # noqa: WPS433

        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        tech_design_ref = frozen_delivered_path_by_type(revision_dir, "lulu-design")
        tech_diagnostic_ref = frozen_delivered_path_by_type(revision_dir, "lulu-approach")
        cycle_type = detect_cycle_type(cycle_id)
        dimensions = select_dimension_defs(
            cycle_type=cycle_type,
            dimension_defs_dir=self.dimension_defs_dir(),
            tech_design_ref=tech_design_ref,
            tech_diagnostic_ref=tech_diagnostic_ref,
        )
        return compose_corpus(
            corpus_id=LULU_PLAN_COMPOSED_CORPUS_ID,
            corpus_version=LULU_PLAN_COMPOSED_CORPUS_VERSION,
            scope="lulu-plan",
            dimensions=dimensions,
        )

    def dimension_defs_dir(self) -> Path:
        return shell_path(load_profile(_WORKFLOW_ID), "dimension_defs_dir")

    @staticmethod
    def _empty_corpus_bind() -> dict[str, str]:
        return {
            "tpt_intent_eval_framework_url": "",
            "tpt_tech_conformance_url": "",
            "upstream_doc_path": "",
        }

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        from subagent_config import detect_platform, get_stage_config_bucket  # noqa: WPS433

        plat = detect_platform(None)
        section = get_stage_config_bucket(project_root.resolve(), "lulu-plan", "eval", plat)
        if not section:
            return self._empty_corpus_bind()
        cycle_type = detect_cycle_type(cycle_id)
        intent_key = intent_eval_config_key(cycle_type)
        tpt_intent_eval_framework_url = str(
            section.get(intent_key, "")
            or section.get("tpt_intent_eval_framework_url", ""),
        ).strip()
        tpt_tech_conformance_url = str(
            section.get("tpt_tech_conformance_url", "")
        ).strip()
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        tech_design_path = frozen_delivered_path_by_type(revision_dir, "lulu-design")
        tech_diagnostic_path = frozen_delivered_path_by_type(revision_dir, "lulu-approach")
        upstream_doc_path = tech_design_path or tech_diagnostic_path
        return {
            "tpt_intent_eval_framework_url": tpt_intent_eval_framework_url,
            "tpt_tech_conformance_url": tpt_tech_conformance_url,
            "upstream_doc_path": upstream_doc_path,
        }

    def detect_cycle_type(self, cycle_id: str) -> str:
        return detect_cycle_type(cycle_id)

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
