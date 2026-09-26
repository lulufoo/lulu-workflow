#!/usr/bin/env python3
"""Tests for compose_session profile-aware paths (lulu-design)."""

from __future__ import annotations

import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import SESSION  # noqa: E402
from workflow_paths import EVAL_SCRIPTS  # noqa: E402

sys.path.insert(0, str(SESSION))
sys.path.insert(0, str(EVAL_SCRIPTS))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()
_TECH_DESIGN_EVAL = (
    Path(__file__).resolve().parents[3] / "lulu-design" / "scripts" / "eval"
)
if str(_TECH_DESIGN_EVAL) not in sys.path:
    sys.path.insert(0, str(_TECH_DESIGN_EVAL))
from compose_eval_adapter import ComposeEvalAdapter  # noqa: E402
from tech_design_eval_contributor import TechDesignEvalContributor  # noqa: E402
from compose_session import (  # noqa: E402
    eval_workflow_id,
    load_active_doc_for_profile,
    load_document_presentation,
    stage_name,
    workflow_state_path,
)
from session_info import session_snapshot, stage_transitions  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402
from workflow_state_schema import init_compose_session  # noqa: E402
from init_working_helpers import init_working_ready, mark_focus_intake_done  # noqa: E402
from framework_template_sources import tech_design_feature_role_instance  # noqa: E402
from test_template_data import seed_template_cache  # noqa: E402

_CYCLE = "feature-composesession001-abc12345"
_PROFILE = "lulu-design"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_design_role_cache(tmp_path: Path) -> None:
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_feature_role_instance_url",
        tech_design_feature_role_instance(),
    )


def _seed_design_session(tmp_path: Path) -> None:
    _seed_design_role_cache(tmp_path)
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    base = tmp_path / _CACHE / _CYCLE / "lulu-design"
    revision = base / "revision1"
    revision.mkdir(parents=True)
    ws = revision / "workflow-state.md"
    init_working_ready(ws, mode="tech")
    (revision / "L1" / "design-doc.md").write_text(
        "---\n\n# Design X\n\nSummary for design session.\n",
        encoding="utf-8",
    )


class TestComposeSessionTechDesign:
    def test_stage_name_matches_profile(self):
        assert stage_name(_PROFILE) == "lulu-design"

    def test_eval_workflow_id(self):
        assert eval_workflow_id(_PROFILE) == "lulu-design"

    def test_workflow_state_path(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        ws = workflow_state_path(_CYCLE, tmp_path, _PROFILE)
        assert ws.as_posix().endswith("lulu-design/revision1/workflow-state.md")
        assert ws.exists()

    def test_session_snapshot(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        payload = session_snapshot(_CYCLE, tmp_path, profile_id=_PROFILE)
        assert payload["profile_id"] == "lulu-design"
        assert set(payload["role"]) == {"role_prompt"}
        assert payload["role"]["role_prompt"].startswith("You are acting")
        assert payload["compose_doc"]["path"].endswith("L1/design-doc.md")
        assert payload["compose_doc"]["title"] == "Design X"
        assert payload["compose_doc"]["status"] == "ready"

    def test_session_snapshot_split_locked_without_design_doc(self, tmp_path: Path):
        """Topology locked in Split; L1/design-doc.md not yet seeded."""
        from init_working_helpers import lock_single_l1_tree  # noqa: WPS433

        seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
        _seed_design_role_cache(tmp_path)
        base = tmp_path / _CACHE / _CYCLE / "lulu-design"
        revision = base / "revision1"
        revision.mkdir(parents=True)
        ws = revision / "workflow-state.md"
        init_compose_session(ws, mode="tech")
        lock_single_l1_tree(revision)
        # No L1/design-doc.md
        payload = session_snapshot(_CYCLE, tmp_path, profile_id=_PROFILE)
        assert payload["workflow_state"]["current_state"] == "Split"
        assert payload["compose_doc"]["status"] == "pending"
        assert payload["compose_doc"]["revision"] == 1
        assert payload["compose_doc"]["path"].endswith("L1/design-doc.md")
        assert payload["compose_doc"]["title"] == ""
        assert set(payload["role"]) == {"role_prompt"}
        assert payload["role"]["role_prompt"].startswith("You are acting")

    def test_stage_transitions(self, tmp_path: Path):
        seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
        payload = stage_transitions(_CYCLE, tmp_path, profile_id=_PROFILE)
        assert payload["profile_id"] == "lulu-design"
        assert payload["next_stages"] == ["lulu-plan"]

    def test_adapter_enter_evaluating_does_not_write_evaluate_state(
        self, tmp_path: Path
    ):
        _seed_design_session(tmp_path)
        rev = tmp_path / _CACHE / _CYCLE / "lulu-design" / "revision1"
        mark_focus_intake_done(rev)
        adapter = ComposeEvalAdapter(
            workflow_id="lulu-design",
            contributor=TechDesignEvalContributor(),
        )
        result = adapter.enter_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_state"] == "Working"
        assert result["phase"] == "evaluating"
        es = (
            tmp_path
            / _CACHE
            / _CYCLE
            / "lulu-design"
            / "revision1"
            / "L1"
            / "evaluate-state.md"
        )
        assert not es.exists()

    def test_load_document_presentation(self, tmp_path: Path):
        _seed_design_session(tmp_path)
        doc = load_document_presentation(_CYCLE, tmp_path, _PROFILE)
        assert doc["path"].endswith("L1/design-doc.md")
        assert load_active_doc_for_profile(_CYCLE, tmp_path, _PROFILE) == 1
