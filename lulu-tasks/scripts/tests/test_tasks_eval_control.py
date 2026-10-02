#!/usr/bin/env python3
"""Corpus, target publication, and route tests for lulu-tasks full-remediation eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_EVAL_ADAPTER = _SCRIPTS / "eval"
_EVAL_SCRIPTS = Path(__file__).resolve().parents[3] / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_ADAPTER, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from tasks_eval_adapter import TasksEvalAdapter  # noqa: E402
from tt_eval_control import cmd_begin_pass, cmd_route_remediation_result  # noqa: E402
from tt_eval_runtime_schema import (  # noqa: E402
    DIMENSIONS,
    allocate_lease,
    evaluate_dir,
    load_runtime,
    runtime_path,
)
from tt_eval_target_schema import eval_target_path, split_eval_target  # noqa: E402
from tt_workflow_common import CACHE_DIR, CACHE_SUBDIR  # noqa: E402

_ALL_DIMENSIONS = list(DIMENSIONS)
_TASK_BODY = "# t1\n\nAcceptance: returns ok.\n"
_REVIEW = """---
schema_version: 3
dimension_id: compliance-crosscheck
round_token: rt-1
---

| ID | root_cause | handling_mode | sot_ref | location | severity | evidence | description | status | decision | resolution |
|----|------------|---------------|---------|----------|----------|----------|-------------|--------|----------|------------|
| e1-1 | WO-MISS | direct | — | task-list.md | high | "digest" | no task carries digest | pending | — | — |
| e1-2 | WO-ERROR | direct | — | tasks/t1/task.md | low | "ok" | fixed in place | resolved | fix | done |
"""


def _emit(fn, *args, **kwargs) -> dict:
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kwargs)
    payload = json.loads(buf.getvalue())
    assert code == (0 if payload.get("ok") else 1)
    return payload


def _seed(project_root: Path, cycle_id: str) -> Path:
    tech = project_root / "tech-doc.md"
    tech.write_text("# Deliverable\n\nThe unit returns ok.\n", encoding="utf-8")
    base = project_root / CACHE_DIR / cycle_id / CACHE_SUBDIR
    session = base / "r1"
    session.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (session / "workflow-state.md").write_text(
        "---\nversion: 1\nworkflow: lulu-tasks\ncurrent_state: Evaluating\n"
        f"evaluate_round: 1\ntech_ref: {tech.resolve().as_posix()}\n---\n",
        encoding="utf-8",
    )
    (session / "task-list.md").write_text("# Tasks\n\n- t1\n", encoding="utf-8")
    task = session / "tasks" / "t1"
    task.mkdir(parents=True)
    (task / "task.md").write_text(_TASK_BODY, encoding="utf-8")
    return session


def _arm(project_root: Path, cycle_id: str, *, evaluate_round: int = 1) -> tuple[Path, dict]:
    """Enter evaluating with a lease and a rendered EvalTarget; return (session, runtime)."""
    adapter = TasksEvalAdapter()
    session = adapter.session_dir(cycle_id, project_root)
    adapter.ensure_eval_target(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session))
    runtime["focus_phase"] = "evaluating"
    runtime["evaluate_round"] = evaluate_round
    runtime = allocate_lease(session, runtime)
    adapter.save_runtime(cycle_id, project_root, runtime)
    return session, runtime


def _stage(runtime: dict, name: str, text: str) -> Path:
    staged = Path(runtime["write_staging_dir"]) / name
    staged.write_text(text, encoding="utf-8")
    return staged


def _digest(path: Path) -> str:
    from eval_admission import file_digest

    return file_digest(path)


def test_corpus_holds_every_dimension_with_distinct_review_paths(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-corpus"
    _seed(tmp_path, cycle_id)
    corpus = TasksEvalAdapter().resolve_eval_corpus(cycle_id, tmp_path)
    assert [dim["id"] for dim in corpus["dimensions"]] == _ALL_DIMENSIONS
    assert corpus["dimension_dispatch"] == "parallel"
    outputs = [dim["review"]["output_path"] for dim in corpus["dimensions"]]
    assert outputs == ["tasks-review-e{M}1.md", "tasks-review-e{M}2.md"]


def test_begin_pass_refused_while_probing(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-busy"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["pass_id"] == 1
    _arm(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is False


def test_begin_eval_round_dispatches_every_dimension_as_full_remediation(tmp_path: Path) -> None:
    import eval_control
    from eval_adapter_config import load_adapter_config_file, load_eval_adapter_from_config

    cycle_id = "tasks-eval-admit"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    profile = Path(__file__).resolve().parents[2] / "eval" / "eval-profile.json"
    config = load_adapter_config_file(profile)
    assert config.eval_capability == "full-remediation"
    adapter = load_eval_adapter_from_config(config)
    adapter_token = eval_control._ADAPTER_CTX.set(adapter)
    workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-tasks")
    handoff_token = eval_control._HANDOFF_CTX.set(None)
    try:
        started = eval_control.begin_eval_round(cycle_id, tmp_path)
    finally:
        eval_control._ADAPTER_CTX.reset(adapter_token)
        eval_control._WORKFLOW_ID_CTX.reset(workflow_token)
        eval_control._HANDOFF_CTX.reset(handoff_token)
    assert started.get("ok") is True, started
    assert started.get("dispatch") == _ALL_DIMENSIONS
    handoff = adapter.request_eval_handoff(cycle_id, tmp_path)
    policy = handoff["context"]["policy_context"]
    assert policy["eval_capability"] == "full-remediation"
    assert policy["completion_mode"] == "return_to_caller"


def test_split_is_the_inverse_of_render(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-split"
    _seed(tmp_path, cycle_id)
    session, _runtime = _arm(tmp_path, cycle_id)
    chapters = split_eval_target(eval_target_path(session).read_text(encoding="utf-8"))
    assert list(chapters) == ["tech-doc", "task-list", "task-t1"]
    assert chapters["task-t1"] == _TASK_BODY.strip()


def test_commit_splits_task_chapter_back_and_publishes_staged_bytes(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-commit"
    _seed(tmp_path, cycle_id)
    session, runtime = _arm(tmp_path, cycle_id)
    target = eval_target_path(session)
    base = _digest(target)
    fixed = target.read_text(encoding="utf-8").replace("Acceptance: returns ok.", "Acceptance: returns ok (tech-doc §1).")
    staged = _stage(runtime, "op-target.staged", fixed)
    result = TasksEvalAdapter().commit_eval_target(
        cycle_id, tmp_path, staged_target_path=staged, base_digest=base, lease_id=runtime["active_lease_id"]
    )
    assert result["ok"] is True, result
    assert result["changed_chapters"] == ["task-t1"]
    assert target.read_bytes() == staged.read_bytes()
    assert result["target_digest"] == _digest(staged)
    task_md = session / "tasks" / "t1" / "task.md"
    assert task_md.read_text(encoding="utf-8") == "# t1\n\nAcceptance: returns ok (tech-doc §1).\n"
    assert (session / "task-list.md").read_text(encoding="utf-8") == "# Tasks\n\n- t1\n"


def test_commit_rejects_task_list_and_chapter_set_changes(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-scope"
    _seed(tmp_path, cycle_id)
    session, runtime = _arm(tmp_path, cycle_id)
    target = eval_target_path(session)
    base = _digest(target)
    original = target.read_text(encoding="utf-8")
    adapter = TasksEvalAdapter()
    lease = runtime["active_lease_id"]

    split_list = _stage(runtime, "list.staged", original.replace("- t1\n", "- t1\n- t2\n"))
    rejected = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=split_list, base_digest=base, lease_id=lease)
    assert rejected["ok"] is False
    assert rejected["error"].startswith("tasks-scope-rejected: task-list chapter changed")

    new_task = _stage(runtime, "new.staged", original + "\n<!-- chapter:task-t2 -->\n\n# t2\n")
    rejected = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=new_task, base_digest=base, lease_id=lease)
    assert rejected["ok"] is False
    assert rejected["error"].startswith("tasks-scope-rejected: chapters added or removed")

    tech = _stage(runtime, "tech.staged", original.replace("The unit returns ok.", "The unit returns fail."))
    rejected = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=tech, base_digest=base, lease_id=lease)
    assert rejected["ok"] is False
    assert rejected["error"].startswith("tasks-scope-rejected: tech-doc chapter changed")

    assert target.read_text(encoding="utf-8") == original
    assert (session / "tasks" / "t1" / "task.md").read_text(encoding="utf-8") == _TASK_BODY


def test_commit_rejects_wrong_lease_and_stale_digest(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-cas"
    _seed(tmp_path, cycle_id)
    session, runtime = _arm(tmp_path, cycle_id)
    target = eval_target_path(session)
    staged = _stage(runtime, "op.staged", target.read_text(encoding="utf-8").replace("Acceptance: returns ok.", "Acceptance: returns ok!"))
    adapter = TasksEvalAdapter()
    wrong_lease = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=staged, base_digest=_digest(target), lease_id="other")
    assert wrong_lease["ok"] is False
    stale = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=staged, base_digest="0" * 64, lease_id=runtime["active_lease_id"])
    assert stale["ok"] is False
    outside = tmp_path / "outside.staged"
    outside.write_text(staged.read_text(encoding="utf-8"), encoding="utf-8")
    escaped = adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=outside, base_digest=_digest(target), lease_id=runtime["active_lease_id"])
    assert escaped["ok"] is False


def test_restore_rolls_task_file_back(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-restore"
    _seed(tmp_path, cycle_id)
    session, runtime = _arm(tmp_path, cycle_id)
    target = eval_target_path(session)
    lease = runtime["active_lease_id"]
    adapter = TasksEvalAdapter()
    snapshot = _stage(runtime, "snapshot", target.read_text(encoding="utf-8"))
    staged = _stage(runtime, "op.staged", target.read_text(encoding="utf-8").replace("Acceptance: returns ok.", "Acceptance: returns ok!"))
    assert adapter.commit_eval_target(cycle_id, tmp_path, staged_target_path=staged, base_digest=_digest(target), lease_id=lease)["ok"]
    restored = adapter.restore_eval_target(cycle_id, tmp_path, snapshot_path=snapshot, expected_current_digest=_digest(target), lease_id=lease)
    assert restored["ok"] is True, restored
    assert target.read_bytes() == snapshot.read_bytes()
    assert (session / "tasks" / "t1" / "task.md").read_text(encoding="utf-8") == _TASK_BODY


def test_route_remediation_complete_is_ready(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-ready"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    _arm(tmp_path, cycle_id)
    routed = _emit(
        cmd_route_remediation_result,
        tmp_path,
        cycle_id,
        result={"ok": True, "command": "remediation-complete", "eval_phase": "done", "eval_status": "done"},
    )
    assert routed == {"ok": True, "disposition": "ready", "issues": []}
    runtime = load_runtime(runtime_path(TasksEvalAdapter().session_dir(cycle_id, tmp_path)))
    assert runtime["focus_phase"] == "pending"
    assert runtime["last_outcome"] == "pass"


def test_route_scope_rejection_returns_to_drafting_with_pending_rows(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-reject"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    session, _runtime = _arm(tmp_path, cycle_id, evaluate_round=2)
    round_dir = evaluate_dir(session, 2)
    round_dir.mkdir(parents=True)
    (round_dir / "tasks-review-e21.md").write_text(_REVIEW, encoding="utf-8")
    routed = _emit(
        cmd_route_remediation_result,
        tmp_path,
        cycle_id,
        result={"ok": False, "command": "apply-remediation", "reason": "tasks-scope-rejected: task-list chapter changed"},
    )
    assert routed["disposition"] == "drafting"
    ids = [issue["id"] for issue in routed["issues"]]
    assert ids == ["scope", "e1-1"]
    assert routed["issues"][0]["location"] == "task-list.md"
    assert routed["issues"][1]["description"] == "no task carries digest"
    runtime = load_runtime(runtime_path(session))
    assert runtime["focus_phase"] == "pending"
    assert runtime["last_disposition"] == "drafting"
    assert len(runtime["last_issues"]) == 2


def test_route_rejects_other_payloads(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-other"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    _arm(tmp_path, cycle_id)
    for payload in (
        {"ok": False, "command": "apply-remediation", "reason": "stale target"},
        {"ok": True, "command": "complete-probe-only", "issues": []},
        {"ok": False, "command": "check-dimension", "reason": "abandoned"},
    ):
        assert _emit(cmd_route_remediation_result, tmp_path, cycle_id, result=payload)["ok"] is False
    runtime = load_runtime(runtime_path(TasksEvalAdapter().session_dir(cycle_id, tmp_path)))
    assert runtime["focus_phase"] == "evaluating"
