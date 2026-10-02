#!/usr/bin/env python3
"""Route tests for lulu-tasks probe-only eval."""

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
from tt_eval_control import cmd_begin_pass, cmd_route_probe_result  # noqa: E402
from tt_eval_runtime_schema import DIMENSIONS, load_runtime, runtime_path  # noqa: E402
from tt_workflow_common import CACHE_DIR, CACHE_SUBDIR  # noqa: E402

_ALL_DIMENSIONS = list(DIMENSIONS)


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
    (task / "task.md").write_text("# t1\n\nAcceptance: returns ok.\n", encoding="utf-8")
    return session


def _arm(project_root: Path, cycle_id: str) -> None:
    adapter = TasksEvalAdapter()
    session = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session))
    runtime["focus_phase"] = "evaluating"
    adapter.save_runtime(cycle_id, project_root, runtime)


def _probe(issues: list[dict]) -> dict:
    return {"ok": True, "command": "complete-probe-only", "issues": issues}


def test_corpus_holds_every_dimension_with_distinct_review_paths(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-corpus"
    _seed(tmp_path, cycle_id)
    corpus = TasksEvalAdapter().resolve_eval_corpus(cycle_id, tmp_path)
    assert [dim["id"] for dim in corpus["dimensions"]] == _ALL_DIMENSIONS
    assert corpus["dimension_dispatch"] == "parallel"
    outputs = [dim["review"]["output_path"] for dim in corpus["dimensions"]]
    assert outputs == ["tasks-review-e{M}1.md", "tasks-review-e{M}2.md"]


def test_finding_from_any_dimension_returns_to_drafting(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-structural"
    _seed(tmp_path, cycle_id)
    started = _emit(cmd_begin_pass, tmp_path, cycle_id)
    assert started["pass_id"] == 1
    _arm(tmp_path, cycle_id)
    issues = [
        {"dimension_id": "compliance-crosscheck", "root_cause": "WO-MISS", "description": "gap"},
        {"dimension_id": "execution-admission", "root_cause": "WO-ERROR", "description": "no signature"},
    ]
    routed = _emit(cmd_route_probe_result, tmp_path, cycle_id, probe_result=_probe(issues))
    assert routed["disposition"] == "drafting"
    assert routed["issues"] == issues
    assert "next_phase" not in routed
    adapter = TasksEvalAdapter()
    runtime = load_runtime(runtime_path(adapter.session_dir(cycle_id, tmp_path)))
    assert runtime["focus_phase"] == "pending"
    assert runtime["last_disposition"] == "drafting"
    assert runtime["last_issues"] == issues
    assert "phase" not in runtime
    assert "probing_phase" not in runtime


def test_clean_round_is_ready_without_a_second_pass(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-advance"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    _arm(tmp_path, cycle_id)
    ready = _emit(cmd_route_probe_result, tmp_path, cycle_id, probe_result=_probe([]))
    assert ready["disposition"] == "ready"
    assert ready["issues"] == []
    assert "next_phase" not in ready


def test_sot_root_cause_is_rejected(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-sot"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    _arm(tmp_path, cycle_id)
    rejected = _emit(
        cmd_route_probe_result,
        tmp_path,
        cycle_id,
        probe_result=_probe([{"root_cause": "SOT-DEFECT", "description": "gap"}]),
    )
    assert rejected["ok"] is False


def test_begin_pass_refused_while_probing(tmp_path: Path) -> None:
    cycle_id = "tasks-eval-busy"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    _arm(tmp_path, cycle_id)
    refused = _emit(cmd_begin_pass, tmp_path, cycle_id)
    assert refused["ok"] is False


def test_begin_eval_round_dispatches_every_dimension(tmp_path: Path) -> None:
    import eval_control
    from eval_adapter_config import load_adapter_config_file, load_eval_adapter_from_config

    cycle_id = "tasks-eval-admit"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_begin_pass, tmp_path, cycle_id)["ok"] is True
    profile = Path(__file__).resolve().parents[2] / "eval" / "eval-profile.json"
    config = load_adapter_config_file(profile)
    assert config.eval_capability == "probe-only"
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
    ready = _emit(cmd_route_probe_result, tmp_path, cycle_id, probe_result=_probe([]))
    assert ready["disposition"] == "ready"
