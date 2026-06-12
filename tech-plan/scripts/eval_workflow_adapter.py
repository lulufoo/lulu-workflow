#!/usr/bin/env python3
"""tech-plan implementation of eval WorkflowAdapter port."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    eval_round_dir,
    load_container_meta,
    tech_doc_path,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)

_EVAL_ROOT = Path(__file__).resolve().parents[2] / "eval" / "scripts"
_WORKFLOW_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_EVAL_ROOT))
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))
from workflow_adapter import SessionContext  # noqa: E402

_MODE_TO_CORPUS_ID = {
    "product": "tech-plan-product",
    "tech": "tech-plan-tech",
}
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
            product_ref=state.get("product_ref", ""),
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
            "tech_doc": (root / tech_doc_path(cycle_id, active_doc)).as_posix(),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root / eval_round_dir(cycle_id, active_doc, evaluate_round)
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in _MODE_TO_CORPUS_ID:
            raise ValueError(
                f"invalid mode: {mode!r} (allowed: {sorted(_MODE_TO_CORPUS_ID)})",
            )
        corpus_id = _MODE_TO_CORPUS_ID[mode]
        from corpus_schema import corpus_ref, load_corpus  # noqa: WPS433

        data = load_corpus(self.corpus_dir() / f"{corpus_id}.json")
        return corpus_ref(data)

    def corpus_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "corpora"

    @staticmethod
    def _empty_corpus_bind() -> dict[str, str]:
        return {
            "ptc_url": "",
            "tpef_url": "",
            "tpt_layer_standards_url": "",
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
        ptc_url = str(section.get("ptc_url", "")).strip()
        tpt_layer_standards_url = str(
            section.get("tpt_layer_standards_url", ""),
        ).strip()
        tpef_url = str(section.get("tpef_url", "")).strip()
        return {
            "ptc_url": ptc_url,
            "tpef_url": tpef_url,
            "tpt_layer_standards_url": tpt_layer_standards_url,
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
        from session_control import start_evaluating  # noqa: WPS433

        return start_evaluating(cycle_id, project_root)
