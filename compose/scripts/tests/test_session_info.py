#!/usr/bin/env python3
"""Tests for lulu-plan session_info.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from transition_table import load_transitions  # noqa: E402
from session_info import (  # noqa: E402
    delivery_preview,
    get_session_info,
    session_snapshot,
    stage_transitions,
)
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests, seed_revision_profile_pointer  # noqa: E402
from workflow_state_schema import save_workflow_state  # noqa: E402
from test_template_data import seed_tech_plan_test_caches  # noqa: E402

import bootstrap  # noqa: F401
from bootstrap import SESSION  # noqa: E402

_SCRIPT = SESSION / "session_info.py"


def _expected_next_stages(cycle_id: str) -> list[str]:
    cycle_type = "topic" if cycle_id.startswith("topic-") else "feature"
    return sorted(load_transitions(cycle_type).get(DEFAULT_COMPOSE_PROFILE_ID, set()))


def _setup_cycle(tmp_path: Path) -> tuple[Path, str]:
    cycle_id = "feat-session-info"
    seed_tech_plan_test_caches(tmp_path)
    seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
    base = tmp_path / ".cache" / "cursor" / "lulu-workflow" / cycle_id / "lulu-plan"
    revision = base / "revision1"
    revision.mkdir(parents=True)
    seed_revision_profile_pointer(revision)
    (revision / "execution").mkdir(parents=True, exist_ok=True)
    (revision / "execution" / "tech-doc.md").write_text(
        "---\n\n"
        "# Feature X\n\n"
        "<!-- chapter:chap-ov -->\n"
        "## Overview\n\n"
        "Deliver a unified session info facade.\n\n"
        "<!-- chapter:chap-kd -->\n"
        "## Key decisions\n\n"
        "KD body.\n",
        encoding="utf-8",
    )
    from workflow_state_schema import init_compose_session  # noqa: WPS433

    ws_path = revision / "workflow-state.md"
    init_compose_session(ws_path, mode="product")
    save_workflow_state(ws_path, {"current_state": "ReadyForDelivery"})
    return tmp_path, cycle_id


class TestDeliveryPreview:
    def test_returns_delivery_fields(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = delivery_preview(cycle_id, project_root)
        assert payload["ok"] is True
        assert payload["view"] == "delivery-preview"
        assert payload["active_doc"] == 1
        assert payload["current_state"] == "ReadyForDelivery"
        assert payload["compose_doc"]["title"] == "Feature X"
        assert "session info facade" in payload["compose_doc"]["summary"]
        assert payload["compose_doc"]["path"].endswith("revision1/execution/tech-doc.md")

    def test_rejects_non_ready_for_delivery_state(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        from workflow_state_schema import init_compose_session, resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        init_compose_session(ws_path, mode="tech")
        payload = delivery_preview(cycle_id, project_root)
        assert payload["ok"] is False
        assert payload["command"] == "delivery-preview"
        assert payload["current_state"] == "Working"
        assert "ReadyForDelivery" in payload["message"]


class TestSessionSnapshot:
    def test_returns_workflow_and_compose_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = session_snapshot(cycle_id, project_root)
        assert payload["view"] == "session"
        assert payload["pipeline"]["inductive"] is True
        assert payload["pipeline"]["code_grounding"] is True
        assert payload["pipeline"]["post_writing_options"] == ["freeedit", "evaluate"]
        assert payload["demand_manifest"] is None
        assert set(payload["role"]) == {"role_prompt"}
        assert payload["role"]["role_prompt"].startswith("You are acting")
        assert payload["revision_dir"] == (
            project_root
            / ".cache"
            / "cursor"
            / "lulu-workflow"
            / cycle_id
            / "lulu-plan"
            / "revision1"
        ).resolve().as_posix()
        assert payload["workflow_state"]["mode"] == "product"
        assert payload["compose_doc"]["revision"] == 1
        assert payload["compose_doc"]["status"] == "ready"

    def test_split_without_compose_doc_returns_pending(self, tmp_path: Path):
        """Working / pre-Writing: session view must not require design-doc."""
        cycle_id = "feat-session-info-split"
        seed_tech_plan_test_caches(tmp_path)
        seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
        base = tmp_path / ".cache" / "cursor" / "lulu-workflow" / cycle_id / "lulu-plan"
        revision = base / "revision1"
        revision.mkdir(parents=True)
        seed_revision_profile_pointer(revision)
        from workflow_state_schema import init_compose_session  # noqa: WPS433

        init_compose_session(revision / "workflow-state.md", mode="tech")
        # No tech-doc.md — mirrors post-start Working before Writing.
        payload = session_snapshot(cycle_id, tmp_path)
        assert payload["view"] == "session"
        assert payload["revision_dir"] == revision.resolve().as_posix()
        assert payload["workflow_state"]["current_state"] == "Working"
        assert payload["compose_doc"]["revision"] == 1
        assert payload["compose_doc"]["status"] == "pending"
        assert payload["compose_doc"]["title"] == ""
        assert payload["compose_doc"]["summary"] == ""
        assert payload["compose_doc"]["path"].endswith("revision1/execution/tech-doc.md")
        assert set(payload["role"]) == {"role_prompt"}
        assert payload["role"]["role_prompt"].startswith("You are acting")


class TestStageTransitions:
    def test_matches_transition_table_for_feature(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = stage_transitions(cycle_id, project_root)
        assert payload == {
            "profile_id": "lulu-plan",
            "next_stages": _expected_next_stages(cycle_id),
        }

    def test_matches_transition_table_for_topic(self, tmp_path: Path):
        project_root, _ = _setup_cycle(tmp_path)
        cycle_id = "topic-session-info"
        seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
        payload = stage_transitions(cycle_id, project_root)
        assert payload == {
            "profile_id": "lulu-plan",
            "next_stages": _expected_next_stages(cycle_id),
        }


class TestGetSessionInfo:
    def test_unknown_view_raises(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        with pytest.raises(ValueError, match="unknown view"):
            get_session_info(cycle_id, project_root, view="invalid")


class TestCli:
    def test_delivery_preview_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "delivery-preview",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["view"] == "delivery-preview"
        assert payload["compose_doc"]["title"] == "Feature X"

    def test_delivery_preview_cli_failure(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        from workflow_state_schema import init_compose_session, resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        init_compose_session(ws_path, mode="tech")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "delivery-preview",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["command"] == "delivery-preview"

    def test_session_view_cli_ok_when_doc_missing(self, tmp_path: Path):
        cycle_id = "feat-session-info-cli-pending"
        seed_tech_plan_test_caches(tmp_path)
        seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
        base = tmp_path / ".cache" / "cursor" / "lulu-workflow" / cycle_id / "lulu-plan"
        revision = base / "revision1"
        revision.mkdir(parents=True)
        seed_revision_profile_pointer(revision)
        from workflow_state_schema import init_compose_session  # noqa: WPS433

        init_compose_session(revision / "workflow-state.md", mode="tech")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(tmp_path),
                "--view",
                "session",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["compose_doc"]["status"] == "pending"
        assert payload["workflow_state"]["current_state"] == "Working"
        assert set(payload["role"]) == {"role_prompt"}
        assert payload["role"]["role_prompt"].startswith("You are acting")

    def test_stage_transitions_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "stage-transitions",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload == {
            "profile_id": "lulu-plan",
            "next_stages": _expected_next_stages(cycle_id),
        }
