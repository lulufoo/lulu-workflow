#!/usr/bin/env python3
"""Tests for tech-code start.py task-list parsing and startup handoff."""

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from session_state_schema import load_session_state  # noqa: E402
from start import parse_work_order_task_list  # noqa: E402
from workflow_state_schema import load_workflow_state  # noqa: E402

_START = _SCRIPTS / "start.py"
_FID = "20260604102312-e2b86e89"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_FEATURE_CYCLE = [
    "product-diagnostic", "product-plan", "tech-diagnostic",
    "tech-plan", "tech-work-order", "tech-code",
]


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def _make_cycles_json(cache_dir: Path, cycle_id: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cj = cache_dir / "cycles.json"
    data = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    data[cycle_id] = {"name": "Test Cycle", "execution_mode": "copilot"}
    cj.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_cycle_state(cache_dir: Path, cycle_id: str, stage: str) -> None:
    p = cache_dir / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"current_stage": stage, "updated_at": "2026-06-01T00:00:00+00:00"}),
        encoding="utf-8",
    )


def _make_session(cache_dir: Path, cycle_id: str, stage: str, revision: str, state: str) -> None:
    workflow_scripts = _SCRIPTS.parents[1] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from hook_guard import _stage_subdir, _STAGE_FLAT  # noqa: E402

    subdir = _stage_subdir(stage)
    if stage in _STAGE_FLAT:
        session_dir = cache_dir / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
    else:
        rev_name = f"revision{revision.lstrip('r')}"
        session_dir = cache_dir / cycle_id / subdir / rev_name
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _all_prior_delivered(cache_dir: Path, cycle_id: str, to_stage: str) -> None:
    idx = _FEATURE_CYCLE.index(to_stage)
    prior = _FEATURE_CYCLE[:idx]
    for stage in prior:
        _make_session(cache_dir, cycle_id, stage, "r1", "Delivered")
    if prior:
        _make_cycle_state(cache_dir, cycle_id, prior[-1])


def _seed_work_order_task_list(tmp_path: Path, content: str) -> None:
    cd = _cache_dir(tmp_path)
    wo_dir = cd / _FID / "tech" / "work-order"
    wo_dir.mkdir(parents=True, exist_ok=True)
    (wo_dir / "session-state.md").write_text(
        "---\nactive_doc: 1\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    r1 = wo_dir / "r1"
    r1.mkdir(parents=True, exist_ok=True)
    (r1 / "task-list.md").write_text(content, encoding="utf-8")


def _seed_gate_and_handoff(tmp_path: Path, task_list_content: str) -> None:
    cd = _cache_dir(tmp_path)
    _make_cycles_json(cd, _FID)
    _all_prior_delivered(cd, _FID, "tech-code")
    _seed_work_order_task_list(tmp_path, task_list_content)


def test_parse_work_order_task_list_accepts_letter_suffix_ids_and_escaped_pipes():
    content = """# Task List

| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
| --- | --- | --- | --- | --- |
| t10 | workflow-config.json nested product-plan.shaping\\|spec | `skill-config/lulu-dev-workflow/workflow-config.json` | t7 | 是 |
| t12b | product-plan/SKILL.md shaping/spec 双路径 + G6 规则 | `product-plan/SKILL.md` | t12 | 是 |
| t16c | [P2] tech-code/SKILL.md gate-model 门控步骤 | `tech-code/SKILL.md` | t6, t13 | 是 |
"""
    tasks = parse_work_order_task_list(content)

    assert [task["id"] for task in tasks] == ["t10", "t12b", "t16c"]
    assert tasks[0]["title"] == "workflow-config.json nested product-plan.shaping|spec"
    assert tasks[0]["target_file"] == "skill-config/lulu-dev-workflow/workflow-config.json"
    assert tasks[1]["depends"] == ["t12"]
    assert tasks[2]["depends"] == ["t6", "t13"]
    assert all(task["tdd_exempt"] for task in tasks)


def test_cli_generates_full_code_task_list_for_complex_task_ids(tmp_path):
    task_list_content = """# Task List

| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
| --- | --- | --- | --- | --- |
| t1 | cycle_init.py mode slug 重命名 + 测试 | `scripts/cycle_init.py`, `scripts/test_cycle_init.py` | — | 否 |
| t10 | workflow-config.json nested product-plan.shaping\\|spec | `skill-config/lulu-dev-workflow/workflow-config.json` | t7 | 是 |
| t12b | product-plan/SKILL.md shaping/spec 双路径 + G6 规则 | `product-plan/SKILL.md` | t12 | 是 |
| t16c | [P2] tech-code/SKILL.md gate-model 门控步骤 | `tech-code/SKILL.md` | t6, t13 | 是 |
"""
    _seed_gate_and_handoff(tmp_path, task_list_content)

    result = subprocess.run(
        [
            sys.executable,
            str(_START),
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            _FID,
        ],
        capture_output=True,
        text=True,
        env=_ENV_COPILOT,
        cwd=str(_SCRIPTS),
    )

    assert result.returncode == 0, result.stderr

    ws_path = (
        tmp_path
        / ".cache"
        / "copilot"
        / "lulu-dev-workflow"
        / _FID
        / "tech"
        / "code"
        / "s1"
        / "workflow-state.md"
    )
    ws = load_workflow_state(ws_path)
    assert ws["current_state"] == "Preparing"
    assert ws["mode"] == "work-order"
    assert ws["task_list_ref"]

    generated = (
        tmp_path
        / ".cache"
        / "copilot"
        / "lulu-dev-workflow"
        / _FID
        / "tech"
        / "code"
        / "s1"
        / "code-task-list.md"
    )
    content = generated.read_text(encoding="utf-8")

    assert "total: 4" in content
    assert "t12b" in content
    assert "t16c" in content
    assert "product-plan.shaping|spec" in content


def test_cli_errors_when_work_order_task_list_missing(tmp_path):
    cd = _cache_dir(tmp_path)
    _make_cycles_json(cd, _FID)
    _all_prior_delivered(cd, _FID, "tech-code")
    wo_dir = cd / _FID / "tech" / "work-order"
    wo_dir.mkdir(parents=True, exist_ok=True)
    (wo_dir / "session-state.md").write_text(
        "---\nactive_doc: 1\nupdated_at: 2026-06-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_START),
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            _FID,
        ],
        capture_output=True,
        text=True,
        env=_ENV_COPILOT,
        cwd=str(_SCRIPTS),
    )

    assert result.returncode != 0
    assert "task-list.md 不存在" in result.stderr


def test_cli_creates_new_round_when_active_preparing(tmp_path):
    task_list_content = """# Task List

| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
| --- | --- | --- | --- | --- |
| t1 | first task | `a.py` | — | 否 |
"""
    _seed_gate_and_handoff(tmp_path, task_list_content)

    first = subprocess.run(
        [
            sys.executable,
            str(_START),
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            _FID,
        ],
        capture_output=True,
        text=True,
        env=_ENV_COPILOT,
        cwd=str(_SCRIPTS),
    )
    assert first.returncode == 0, first.stderr

    ss_path = (
        tmp_path
        / ".cache"
        / "copilot"
        / "lulu-dev-workflow"
        / _FID
        / "tech"
        / "code"
        / "session-state.md"
    )
    assert load_session_state(ss_path) == 1

    second = subprocess.run(
        [
            sys.executable,
            str(_START),
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            _FID,
        ],
        capture_output=True,
        text=True,
        env=_ENV_COPILOT,
        cwd=str(_SCRIPTS),
    )
    assert second.returncode == 0, second.stderr
    assert "superseding s1 in Preparing" in second.stderr

    assert load_session_state(ss_path) == 2

    ws_path = (
        tmp_path
        / ".cache"
        / "copilot"
        / "lulu-dev-workflow"
        / _FID
        / "tech"
        / "code"
        / "s2"
        / "workflow-state.md"
    )
    assert load_workflow_state(ws_path)["current_state"] == "Preparing"
