#!/usr/bin/env python3
"""tech-design implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_EVAL_SHELL = Path(__file__).resolve().parent
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
for p in (_KERNEL_SCRIPTS, _EVAL_SHELL, _EVAL_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import EVAL_SCRIPTS, load_profile, shell_path  # noqa: E402

_PROFILE = load_profile("tech-design")
_WORKFLOW_ID = "tech-design"

from session_state_schema import load_active_doc  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    load_container_meta,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    save_workflow_state,
)
from delivered_refs_schema import product_ref_from_state  # noqa: E402

sys.path.insert(0, str(EVAL_SCRIPTS))
from workflow_adapter import SessionContext  # noqa: E402

from tech_design_eval_policy import select_dimension_defs  # noqa: E402

_VALID_EXECUTION_MODES = frozenset({"guided", "autonomous"})


def _session_base_dir(cycle_id: str) -> Path:
    return CACHE_DIR / cycle_id / _PROFILE["cache_subdir"]


def _session_state_path(cycle_id: str) -> Path:
    return _session_base_dir(cycle_id) / "session-state.md"


def _doc_dir(cycle_id: str, doc_round: int) -> Path:
    return _session_base_dir(cycle_id) / f"revision{doc_round}"


def _state_path(cycle_id: str, doc_round: int) -> Path:
    return _doc_dir(cycle_id, doc_round) / "workflow-state.md"


def _design_doc_path(cycle_id: str, doc_round: int) -> Path:
    return _doc_dir(cycle_id, doc_round) / _PROFILE["document"]["filename"]


def _eval_round_dir(cycle_id: str, doc_round: int, evaluate_round: int) -> Path:
    return _doc_dir(cycle_id, doc_round) / f"evaluate{evaluate_round}"


def _active_doc(cycle_id: str, project_root: Path) -> int:
    return load_active_doc(project_root / _session_state_path(cycle_id), default=1)


class TechDesignEvalAdapter:
    """WorkflowAdapter for tech-design cache layout and state machine."""

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return project_root / _state_path(cycle_id, _active_doc(cycle_id, project_root))

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
        active_doc = _active_doc(cycle_id, project_root)
        return project_root / _doc_dir(cycle_id, active_doc) / "evaluate-state.md"

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        return SessionContext(
            active_doc=_active_doc(cycle_id, project_root),
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
        compose_doc = (root / _design_doc_path(cycle_id, active_doc)).as_posix()
        return {
            "compose_doc": compose_doc,
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root / _eval_round_dir(cycle_id, active_doc, evaluate_round)
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: ['product', 'tech'])",
            )
        from corpus_compose import TECH_DESIGN_COMPOSED_CORPUS_REF  # noqa: WPS433

        return TECH_DESIGN_COMPOSED_CORPUS_REF

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        from corpus_compose import (  # noqa: WPS433
            TECH_DESIGN_COMPOSED_CORPUS_ID,
            TECH_DESIGN_COMPOSED_CORPUS_VERSION,
            compose_corpus,
        )

        cycle_type = detect_cycle_type(cycle_id)
        dimensions = select_dimension_defs(
            cycle_type=cycle_type,
            dimension_defs_dir=self.dimension_defs_dir(),
        )
        return compose_corpus(
            corpus_id=TECH_DESIGN_COMPOSED_CORPUS_ID,
            corpus_version=TECH_DESIGN_COMPOSED_CORPUS_VERSION,
            scope="tech-design",
            dimensions=dimensions,
            review_output_prefix="design-review",
        )

    def dimension_defs_dir(self) -> Path:
        return shell_path(_PROFILE, "dimension_defs_dir")

    @staticmethod
    def _empty_corpus_bind() -> dict[str, str]:
        return {
            "tdt_design_quality_framework_url": "",
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
        section = config.get("tech-design")
        if not isinstance(section, dict):
            return self._empty_corpus_bind()
        framework_url = str(
            section.get("tdt_design_quality_framework_url", ""),
        ).strip()
        return {
            "tdt_design_quality_framework_url": framework_url,
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
