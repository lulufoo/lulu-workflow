#!/usr/bin/env python3
"""Tests for kind: action — receipt schema, frontmatter helpers, context, receipt command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_action_receipt_schema import (  # noqa: E402
    load_receipt,
    receipt_path,
    save_receipt,
    validate_receipt,
)
from tc_prepare import _validate_single_task  # noqa: E402
from tc_repo_map_schema import required_target_repos  # noqa: E402
from tc_resolve_task_context import resolve_task_context  # noqa: E402
from tc_task_control import _parse_results, record_receipt_cmd  # noqa: E402
from tc_task_frontmatter import (  # noqa: E402
    describe_effects,
    parse_acceptance_criteria,
    validate_effects,
)
from tc_workflow_state_schema import init_preparing, save_workflow_state  # noqa: E402

_CRITERIA = ["Every todo has a Linear issue", "Missing todos were migrated once"]

_TASK_MD = """---
task_id: t1
title: Todos are migrated to Linear
kind: action
effects: mutates
mutates: [linear]
exit_contract:
  receipt: required
---
# t1

## Section 1: Acceptance Criteria

- [ ] Every todo has a Linear issue
- [x]   Missing todos   were migrated once

## Section 3: Constraints

- [ ] not an acceptance criterion
"""


@pytest.fixture(autouse=True)
def _clean_conversation_id_env(monkeypatch):
    monkeypatch.delenv("LULU_CONVERSATION_ID", raising=False)


def _results(criteria: list[str] = _CRITERIA) -> list[dict]:
    return [{"criterion": c, "evidence": f"LIN-1: {c}", "met": True} for c in criteria]


def _payload(results: list[dict]) -> dict:
    return {
        "version": 2,
        "task_id": "t1",
        "goal": "Todos are migrated to Linear",
        "effects": "mutates: linear",
        "results": results,
    }


class TestReceiptSchema:
    def test_valid_receipt_round_trips(self, tmp_path: Path):
        path = receipt_path(tmp_path, "t1")
        save_receipt(path, _payload(_results()), _CRITERIA)
        assert load_receipt(path, "t1", _CRITERIA)["version"] == 2

    def test_whitespace_differences_still_match(self):
        results = _results(["Every  todo has a Linear issue", "Missing todos were migrated once"])
        assert validate_receipt(_payload(results), "t1", _CRITERIA) == []

    def test_rejects_missing_criterion(self):
        errors = validate_receipt(_payload(_results(_CRITERIA[:1])), "t1", _CRITERIA)
        assert any("no result for acceptance criterion" in e for e in errors)

    def test_rejects_unknown_criterion(self):
        errors = validate_receipt(_payload(_results(_CRITERIA + ["Invented"])), "t1", _CRITERIA)
        assert any("unknown acceptance criterion" in e for e in errors)

    def test_rejects_duplicate_answer(self):
        errors = validate_receipt(_payload(_results(_CRITERIA + _CRITERIA[:1])), "t1", _CRITERIA)
        assert any("more than once" in e for e in errors)

    @pytest.mark.parametrize("evidence", ["", "   ", None, 3])
    def test_rejects_blank_evidence(self, evidence):
        results = _results()
        results[0]["evidence"] = evidence
        errors = validate_receipt(_payload(results), "t1", _CRITERIA)
        assert any("evidence must be a non-empty string" in e for e in errors)

    @pytest.mark.parametrize("met", [False, "true", None])
    def test_rejects_unmet_criterion(self, met):
        results = _results()
        results[1]["met"] = met
        errors = validate_receipt(_payload(results), "t1", _CRITERIA)
        assert any("met must be true" in e for e in errors)

    def test_rejects_task_without_acceptance_criteria(self):
        assert validate_receipt(_payload([]), "t1", []) == ["task has no acceptance criteria"]

    def test_rejects_wrong_version_and_task_id(self):
        data = _payload(_results())
        data["version"] = 1
        data["task_id"] = "t9"
        errors = validate_receipt(data, "t1", _CRITERIA)
        assert "version must be 2" in errors
        assert any("task_id mismatch" in e for e in errors)

    def test_save_refuses_invalid_receipt(self, tmp_path: Path):
        path = receipt_path(tmp_path, "t1")
        with pytest.raises(ValueError, match="no result for acceptance criterion"):
            save_receipt(path, _payload(_results(_CRITERIA[:1])), _CRITERIA)
        assert not path.exists()


class TestFrontmatterHelpers:
    def test_parse_acceptance_criteria_reads_only_section_one(self):
        assert parse_acceptance_criteria(_TASK_MD) == [
            "Every todo has a Linear issue",
            "Missing todos   were migrated once",
        ]

    @pytest.mark.parametrize(
        "fm, expected",
        [
            ({"effects": "read_only"}, []),
            ({"effects": "mutates", "mutates": "[linear, board]"}, []),
            ({}, ["effects must be one of"]),
            ({"effects": "mutates"}, ["non-empty mutates list"]),
            ({"effects": "read_only", "mutates": "[linear]"}, ["must not declare mutates"]),
        ],
    )
    def test_validate_effects(self, fm, expected):
        errors = validate_effects("t1", fm)
        assert len(errors) == len(expected)
        for fragment in expected:
            assert fragment in errors[0]

    def test_describe_effects(self):
        assert describe_effects({"effects": "read_only"}) == "read_only"
        assert (
            describe_effects({"effects": "mutates", "mutates": "[linear, board]"})
            == "mutates: linear, board"
        )


class TestPrepareValidation:
    def _fm(self, **overrides) -> dict:
        fm = {
            "kind": "action",
            "effects": "read_only",
            "exit_contract": {"receipt": "required"},
        }
        fm.update(overrides)
        return fm

    def test_action_without_worktree_is_valid(self):
        assert _validate_single_task("t1", self._fm()) == []

    def test_action_without_worktree_needs_no_repo_bind(self):
        assert required_target_repos([{"task_id": "t1", "target_repo": "", "execution_worktree": ""}]) == set()

    def test_action_with_worktree_needs_target_repo(self):
        errors = _validate_single_task("t1", self._fm(execution_worktree="feature_worktree"))
        assert errors == ["t1: missing target_repo for execution_worktree"]

    def test_action_with_worktree_and_repo_is_valid(self):
        fm = self._fm(execution_worktree="feature_worktree", target_repo="repo-a")
        assert _validate_single_task("t1", fm) == []

    def test_action_requires_effects(self):
        fm = self._fm()
        del fm["effects"]
        assert any("effects must be one of" in e for e in _validate_single_task("t1", fm))

    def test_action_requires_receipt_exit_contract(self):
        errors = _validate_single_task("t1", self._fm(exit_contract={"commit": "required"}))
        assert any("exit_contract.receipt" in e for e in errors)

    def test_coding_still_requires_worktree(self):
        fm = {"kind": "coding", "exit_contract": {}}
        assert "t1: missing execution_worktree" in _validate_single_task("t1", fm)

    def test_verify_kind_is_rejected(self):
        errors = _validate_single_task("t1", {"kind": "verify"})
        assert errors == ["t1: kind must be one of ['coding', 'action'], got 'verify'"]


def _setup_action_cycle(tmp_path: Path, *, task_md: str = _TASK_MD) -> tuple[Path, Path, Path]:
    cycle_dir = tmp_path / "cycle"
    project_root = tmp_path / "project"
    project_root.mkdir()
    wo_dir = cycle_dir / "lulu-tasks"
    (wo_dir / "r1" / "tasks" / "t1").mkdir(parents=True)
    (wo_dir / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (wo_dir / "r1" / "tasks" / "t1" / "task.md").write_text(task_md, encoding="utf-8")

    config_dir = project_root / ".cursor" / "lulu-workflow"
    config_dir.mkdir(parents=True)
    (config_dir / "workflow-config.json").write_text(
        json.dumps({"lulu-code": {"test_command": "echo ok", "git": {}}}), encoding="utf-8"
    )

    session_dir = cycle_dir / "lulu-code" / "s1"
    session_dir.mkdir(parents=True)
    (cycle_dir / "lulu-code" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · task\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (session_dir / "workspace.json").write_text(
        json.dumps(
            {
                "worktree_path": str(worktree.resolve()).rstrip("/") + "/",
                "project_root": str(project_root.resolve()),
                "branch": "wt/feat-test",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    save_workflow_state(ws_path, {"current_state": "Executing", "current_task": "t1", "current_phase": ""})
    return cycle_dir, project_root, session_dir


class TestResolveContext:
    def test_action_without_worktree_runs_in_project_root(self, tmp_path: Path):
        cycle_dir, project_root, _ = _setup_action_cycle(tmp_path)
        ctx = resolve_task_context(cycle_dir, "t1", project_root)
        assert ctx["kind"] == "action"
        assert ctx["worktree_abs_path"] == project_root.resolve().as_posix()
        assert ctx["branch"] == ""
        assert ctx["goal"] == "Todos are migrated to Linear"
        assert ctx["effects"] == "mutates: linear"
        assert ctx["acceptance"] == parse_acceptance_criteria(_TASK_MD)

    def test_action_with_worktree_uses_it(self, tmp_path: Path):
        task_md = _TASK_MD.replace(
            "kind: action\n",
            "kind: action\ntarget_repo: repo-a\nexecution_worktree: feature_worktree\n",
        )
        cycle_dir, project_root, _ = _setup_action_cycle(tmp_path, task_md=task_md)
        ctx = resolve_task_context(cycle_dir, "t1", project_root)
        assert ctx["worktree_abs_path"] == (tmp_path / "wt").resolve().as_posix()
        assert ctx["branch"] == "wt/feat-test"

    def test_coding_context_has_no_action_fields(self, tmp_path: Path):
        task_md = "---\nkind: coding\ntarget_repo: repo-a\nexecution_worktree: feature_worktree\n---\n# t1\n"
        cycle_dir, project_root, _ = _setup_action_cycle(tmp_path, task_md=task_md)
        ctx = resolve_task_context(cycle_dir, "t1", project_root)
        assert not {"goal", "effects", "acceptance"} & set(ctx)


class TestRecordReceipt:
    def test_records_receipt_that_covers_every_criterion(self, tmp_path: Path):
        cycle_dir, project_root, session_dir = _setup_action_cycle(tmp_path)
        criteria = parse_acceptance_criteria(_TASK_MD)
        result = record_receipt_cmd(cycle_dir, "t1", project_root, results=_results(criteria))
        assert result == {"task_id": "t1", "criteria": 2, "ok": True}
        saved = json.loads(receipt_path(session_dir, "t1").read_text(encoding="utf-8"))
        assert saved["goal"] == "Todos are migrated to Linear"
        assert saved["effects"] == "mutates: linear"

    def test_rejects_receipt_missing_a_criterion(self, tmp_path: Path):
        cycle_dir, project_root, session_dir = _setup_action_cycle(tmp_path)
        criteria = parse_acceptance_criteria(_TASK_MD)
        with pytest.raises(ValueError, match="no result for acceptance criterion"):
            record_receipt_cmd(cycle_dir, "t1", project_root, results=_results(criteria[:1]))
        assert not receipt_path(session_dir, "t1").exists()

    def test_rejects_non_action_task(self, tmp_path: Path):
        task_md = "---\nkind: coding\ntarget_repo: repo-a\nexecution_worktree: feature_worktree\n---\n# t1\n"
        cycle_dir, project_root, _ = _setup_action_cycle(tmp_path, task_md=task_md)
        with pytest.raises(ValueError, match="record-receipt is for action tasks"):
            record_receipt_cmd(cycle_dir, "t1", project_root, results=[])


class TestParseResults:
    def test_accepts_list_or_wrapped_list(self):
        assert _parse_results('[{"criterion": "a"}]') == [{"criterion": "a"}]
        assert _parse_results('{"results": [1]}') == [1]

    @pytest.mark.parametrize("raw", ["not json", '{"other": 1}', '"text"'])
    def test_rejects_other_input(self, raw):
        with pytest.raises(ValueError):
            _parse_results(raw)
