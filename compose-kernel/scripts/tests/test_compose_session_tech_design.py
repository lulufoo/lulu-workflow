#!/usr/bin/env python3
"""Tests for compose_session profile-aware paths (tech-design)."""

from __future__ import annotations

import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402
from workflow_paths import EVAL_SCRIPTS  # noqa: E402

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EVAL_SCRIPTS))
_TECH_DESIGN_EVAL = (
    Path(__file__).resolve().parents[3] / "tech-design" / "scripts" / "eval"
)
if str(_TECH_DESIGN_EVAL) not in sys.path:
    sys.path.insert(0, str(_TECH_DESIGN_EVAL))
from tech_design_eval_adapter import TechDesignEvalAdapter  # noqa: E402
from compose_session import (  # noqa: E402
    eval_workflow_id,
    load_active_doc_for_profile,
    load_document_presentation,
    stage_name,
    workflow_state_path,
)
from session_info import session_snapshot, stage_transitions  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402
from workflow_state_schema import init_drafting  # noqa: E402

_CYCLE = "feature-composesession001-abc12345"
_PROFILE = "tech-design"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_design_session(tmp_path: Path) -> None:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    base = tmp_path / _CACHE / _CYCLE / "tech" / "design"
    revision = base / "revision1"
    revision.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws = revision / "workflow-state.md"
    init_drafting(ws, mode="tech")
    (revision / "design-doc.md").write_text(
        "---\n\n# Design X\n\nSummary for design session.\n",
        encoding="utf-8",
    )


class TestComposeSessionTechDesign:
    def test_stage_name_matches_profile(self):
        assert stage_name(_PROFILE) == "tech-design"

    def test_eval_workflow_id(self):
        assert eval_workflow_id(_PROFILE) == "tech-design"

    def test_workflow_state_path(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        ws = workflow_state_path(_CYCLE, tmp_path, _PROFILE)
        assert ws.as_posix().endswith("tech/design/revision1/workflow-state.md")
        assert ws.exists()

    def test_session_snapshot(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        payload = session_snapshot(_CYCLE, tmp_path, profile_id=_PROFILE)
        assert payload["profile_id"] == "tech-design"
        assert payload["compose_doc"]["path"].endswith("design-doc.md")
        assert payload["compose_doc"]["title"] == "Design X"

    def test_stage_transitions(self, tmp_path: Path):
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
        payload = stage_transitions(_CYCLE, tmp_path, profile_id=_PROFILE)
        assert payload["profile_id"] == "tech-design"
        assert payload["next_stages"] == ["tech-plan"]

    def test_adapter_enter_evaluating_creates_evaluate_state(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        adapter = TechDesignEvalAdapter()
        result = adapter.enter_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is True
        es = (
            tmp_path
            / _CACHE
            / _CYCLE
            / "tech"
            / "design"
            / "revision1"
            / "evaluate-state.md"
        )
        assert es.exists()

    def test_load_document_presentation(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        doc = load_document_presentation(_CYCLE, tmp_path, _PROFILE)
        assert doc["path"].endswith("design-doc.md")
        assert load_active_doc_for_profile(_CYCLE, tmp_path, _PROFILE) == 1
