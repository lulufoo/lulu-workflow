#!/usr/bin/env python3
"""tech-plan implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_EVAL_SHELL = Path(__file__).resolve().parent
for p in (_KERNEL_SCRIPTS, _EVAL_SHELL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import EVAL_SCRIPTS, WORKFLOW_SCRIPTS, load_profile, shell_path  # noqa: E402

_PROFILE = load_profile("tech-plan")

from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    eval_round_dir,
    load_container_meta,
)
from workflow_profile_paths import document_path  # noqa: E402
from delivered_refs_schema import product_ref_from_state  # noqa: E402
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

_VALID_EXECUTION_MODES = frozenset({"guided", "autonomous"})


class TechPlanEvalAdapter:
    """WorkflowAdapter for tech-plan cache layout and state machine."""

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return project_root / resolve_workflow_state_path_from_cycle(
            cycle_id, project_root
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
        active_doc = load_active_doc_from_cycle(cycle_id, project_root)
        from workflow_common import doc_dir  # noqa: WPS433

        return project_root / doc_dir(cycle_id, active_doc) / "evaluate-state.md"

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        return SessionContext(
            active_doc=load_active_doc_from_cycle(cycle_id, project_root),
            mode=state["mode"],
            product_ref=product_ref_from_state(state),
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
                root / document_path(cycle_id, active_doc, "tech-plan")
            ).as_posix(),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root / eval_round_dir(cycle_id, active_doc, evaluate_round)
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: ['product', 'tech'])",
            )
        from corpus_compose import COMPOSED_CORPUS_REF  # noqa: WPS433

        return COMPOSED_CORPUS_REF

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        from corpus_compose import (  # noqa: WPS433
            COMPOSED_CORPUS_ID,
            COMPOSED_CORPUS_VERSION,
            compose_corpus,
        )

        state = self.load_workflow_state(cycle_id, project_root)
        mode = state["mode"]
        product_ref = product_ref_from_state(state)
        cycle_type = detect_cycle_type(cycle_id)
        dimensions = select_dimension_defs(
            product_ref=product_ref,
            mode=mode,
            cycle_type=cycle_type,
            dimension_defs_dir=self.dimension_defs_dir(),
        )
        return compose_corpus(
            corpus_id=COMPOSED_CORPUS_ID,
            corpus_version=COMPOSED_CORPUS_VERSION,
            scope="tech-plan",
            dimensions=dimensions,
        )

    def dimension_defs_dir(self) -> Path:
        return shell_path(_PROFILE, "dimension_defs_dir")

    @staticmethod
    def _empty_corpus_bind() -> dict[str, str]:
        return {
            "tpt_product_tech_spec_crosscheck_url": "",
            "tpt_intent_eval_framework_url": "",
        }

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        from subagent_config import detect_platform, resolve_workflow_config_path  # noqa: WPS433

        plat = detect_platform(None)
        config_path = resolve_workflow_config_path(project_root.resolve(), plat)
        if not config_path.exists():
            return self._empty_corpus_bind()
        try:
            import json

            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._empty_corpus_bind()
        section = config.get("tech-plan")
        if not isinstance(section, dict):
            return self._empty_corpus_bind()
        crosscheck_url = str(
            section.get("tpt_product_tech_spec_crosscheck_url", "")
        ).strip()
        cycle_type = detect_cycle_type(cycle_id)
        intent_key = intent_eval_config_key(cycle_type)
        tpt_intent_eval_framework_url = str(
            section.get(intent_key, "")
            or section.get("tpt_intent_eval_framework_url", ""),
        ).strip()
        return {
            "tpt_product_tech_spec_crosscheck_url": crosscheck_url,
            "tpt_intent_eval_framework_url": tpt_intent_eval_framework_url,
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
        from session_evaluating import transition_to_evaluating  # noqa: WPS433

        return transition_to_evaluating(
            cycle_id,
            project_root,
            profile_id=_PROFILE["profile_id"],
        )
