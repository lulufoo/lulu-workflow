#!/usr/bin/env python3
"""Tests for tech-code start.py task-list parsing."""

import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from start import parse_work_order_task_list  # noqa: E402

_START = _SCRIPTS / "start.py"
_FID = "20260604102312-e2b86e89"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def test_parse_work_order_task_list_accepts_letter_suffix_ids_and_escaped_pipes():
    content = """# Task List

| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
| --- | --- | --- | --- | --- |
| t10 | workflow-config.json nested product-plan.shaping\\|spec + template | `skill-config/lulu-dev-workflow/workflow-config.json`, `product-plan/templates/workflow-config.template.json` | t7 | 是 |
| t12b | product-plan/SKILL.md shaping/spec 双路径 + G6 规则 | `product-plan/SKILL.md` | t12 | 是 |
| t16c | [P2] tech-code/SKILL.md gate-model 门控步骤 | `tech-code/SKILL.md` | t6, t13 | 是 |
"""
    tasks = parse_work_order_task_list(content)

    assert [task["id"] for task in tasks] == ["t10", "t12b", "t16c"]
    assert tasks[0]["title"] == "workflow-config.json nested product-plan.shaping|spec + template"
    assert tasks[0]["target_file"] == (
        "skill-config/lulu-dev-workflow/workflow-config.json, "
        "product-plan/templates/workflow-config.template.json"
    )
    assert tasks[1]["depends"] == ["t12"]
    assert tasks[2]["depends"] == ["t6", "t13"]
    assert all(task["tdd_exempt"] for task in tasks)


def test_cli_generates_full_code_task_list_for_complex_task_ids(tmp_path):
    task_list = tmp_path / "task-list.md"
    task_list.write_text(
        """# Task List

| task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
| --- | --- | --- | --- | --- |
| t1 | cycle_init.py mode slug 重命名 + 测试 | `scripts/cycle_init.py`, `scripts/test_cycle_init.py` | — | 否 |
| t10 | workflow-config.json nested product-plan.shaping\\|spec + template | `skill-config/lulu-dev-workflow/workflow-config.json`, `product-plan/templates/workflow-config.template.json` | t7 | 是 |
| t12b | product-plan/SKILL.md shaping/spec 双路径 + G6 规则 | `product-plan/SKILL.md` | t12 | 是 |
| t16c | [P2] tech-code/SKILL.md gate-model 门控步骤 | `tech-code/SKILL.md` | t6, t13 | 是 |
""",
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
            "--task-list-ref",
            str(task_list),
        ],
        capture_output=True,
        text=True,
        env=_ENV_COPILOT,
        cwd=str(_SCRIPTS),
    )

    assert result.returncode == 0, result.stderr

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
    assert "product-plan.shaping|spec + template" in content


def test_cli_requires_task_list_ref(tmp_path):
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
    assert "task-list-ref" in result.stderr
