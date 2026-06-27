#!/usr/bin/env python3
"""Tests for tech-code prepare.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_git_ops import normalize_repo_path  # noqa: E402
from tc_prepare import (  # noqa: E402
    build_worktree_paths,
    ensure_workspace,
    main,
    validate_preparing_to_executing,
    write_workspace,
)
from tc_workflow_state_schema import init_preparing, save_workflow_state  # noqa: E402

_SCRIPT = Path(__file__).resolve().parents[1] / "tc_prepare.py"


def test_build_worktree_paths_returns_expected_values():
    git_cfg = {
        "worktree_base": ".cache/worktrees",
        "branch_pattern": "wt/{type}-{slug}",
        "default_type": "feat",
    }
    paths = build_worktree_paths("abc12345-dead", git_cfg)
    assert paths["worktree_dir"] == ".cache/worktrees/abc12345-dead/"
    assert paths["branch"] == "wt/feat-abc12345-dead"


def test_write_workspace_writes_absolute_paths(tmp_path: Path):
    cycle_dir = tmp_path / ".cache" / "copilot" / "lulu-dev-workflow" / "fid-123"
    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True, exist_ok=True)
    project_root = tmp_path

    paths = {"worktree_dir": ".cache/worktrees/slug-1/", "branch": "wt/feat-slug-1"}
    tasks = [
        {"task_id": "t1", "target_repo": "repo-a", "execution_worktree": "feature_worktree"},
        {"task_id": "t2", "target_repo": "repo-b", "execution_worktree": "extra_repo_worktree"},
    ]

    workspace_path = write_workspace(cycle_dir, 1, "slug-1", paths, tasks, project_root)
    payload = json.loads(workspace_path.read_text(encoding="utf-8"))

    assert payload["worktree_path"].startswith(str(project_root.resolve()))
    assert payload["worktree_path"].endswith("/")
    assert payload["project_root"] == str(project_root.resolve())
    assert payload["extra_worktrees"]["repo-b"]["path"].startswith(str(project_root.resolve()))
    assert payload["extra_worktrees"]["repo-b"]["path"].endswith("/")


def test_write_workspace_extra_repo_only_still_writes_extra_index(tmp_path: Path):
    cycle_dir = tmp_path / ".cache" / "copilot" / "lulu-dev-workflow" / "fid-123"
    project_root = tmp_path
    paths = {"worktree_dir": ".cache/worktrees/slug-1/", "branch": "wt/feat-slug-1"}
    tasks = [
        {"task_id": "t1", "target_repo": "repo-b", "execution_worktree": "extra_repo_worktree"},
    ]

    workspace_path = write_workspace(cycle_dir, 1, "slug-1", paths, tasks, project_root)
    payload = json.loads(workspace_path.read_text(encoding="utf-8"))

    assert payload["primary_repo"] == "repo-b"
    assert payload["extra_worktrees"]["repo-b"]["path"].endswith("slug-1-repo-b/")
    assert payload["extra_worktrees"]["repo-b"]["branch"] == "wt/feat-slug-1-repo-b"


def test_write_workspace_extra_repo_first_does_not_depend_on_repo_order(tmp_path: Path):
    cycle_dir = tmp_path / ".cache" / "copilot" / "lulu-dev-workflow" / "fid-123"
    project_root = tmp_path
    paths = {"worktree_dir": ".cache/worktrees/slug-1/", "branch": "wt/feat-slug-1"}
    tasks = [
        {"task_id": "t1", "target_repo": "repo-b", "execution_worktree": "extra_repo_worktree"},
        {"task_id": "t2", "target_repo": "repo-a", "execution_worktree": "feature_worktree"},
    ]

    workspace_path = write_workspace(cycle_dir, 1, "slug-1", paths, tasks, project_root)
    payload = json.loads(workspace_path.read_text(encoding="utf-8"))

    assert payload["primary_repo"] == "repo-a"
    assert payload["extra_worktrees"]["repo-b"]["path"].endswith("slug-1-repo-b/")
    assert payload["extra_worktrees"]["repo-b"]["branch"] == "wt/feat-slug-1-repo-b"


_TASK_MD = """---
target_repo: repo-a
execution_worktree: feature_worktree
exit_contract:
  commit: required
  commit_ref_md: required
  code_log: required
---
# Task
"""


def _setup_full_preparing_session(tmp_path: Path) -> tuple[Path, Path]:
    cycle_dir = tmp_path / "cycle-id"
    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True)

    wo_dir = cycle_dir / "tech" / "work-order"
    wo_dir.mkdir(parents=True)
    (wo_dir / "session-state.md").write_text(
        "---\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    task_dir = wo_dir / "r1" / "tasks" / "t1"
    task_dir.mkdir(parents=True)
    (task_dir / "task.md").write_text(_TASK_MD, encoding="utf-8")

    (cycle_dir / "tech" / "code" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · task\n", encoding="utf-8")

    config_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True)
    (config_dir / "workflow-config.json").write_text(
        json.dumps({
            "tech-code": {
                "git": {
                    "worktree_base": ".cache/worktrees",
                    "branch_pattern": "wt/{type}-{slug}",
                    "default_type": "feat",
                }
            }
        }),
        encoding="utf-8",
    )

    worktree = tmp_path / "wt"
    worktree.mkdir()
    return cycle_dir, worktree


def _setup_validate_session(tmp_path: Path) -> tuple[Path, Path]:
    cycle_dir = tmp_path / "cycle-id"
    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True)
    (cycle_dir / "tech" / "code" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · task\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    write_workspace(
        cycle_dir,
        1,
        "slug-1",
        {"worktree_dir": str(worktree.relative_to(tmp_path)) + "/", "branch": "wt/feat-slug-1"},
        [{"task_id": "t1", "target_repo": "repo-a", "execution_worktree": "feature_worktree"}],
        tmp_path,
    )
    return cycle_dir, worktree


def _fake_git(monkeypatch, worktree: Path):
    path = str(worktree.resolve())
    real_run = subprocess.run

    def _run(cmd, capture_output=True, text=True, check=False):
        if (
            isinstance(cmd, list)
            and len(cmd) >= 4
            and cmd[0] == "git"
            and cmd[1] == "-C"
            and cmd[3] == "rev-parse"
            and cmd[2].rstrip("/") == path
        ):
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        return real_run(cmd, capture_output=capture_output, text=text, check=check)

    monkeypatch.setattr("tc_git_ops.subprocess.run", _run)


def test_validate_preparing_to_executing(tmp_path: Path, monkeypatch):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    _fake_git(monkeypatch, worktree)
    payload = validate_preparing_to_executing(cycle_dir)
    assert payload["current_state"] == "Executing"
    assert payload["current_task"] == "t1"
    assert payload["worktree_path"].startswith(str(tmp_path.resolve()))


def test_validate_idempotent_executing(tmp_path: Path, monkeypatch):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    _fake_git(monkeypatch, worktree)
    validate_preparing_to_executing(cycle_dir)
    payload = validate_preparing_to_executing(cycle_dir)
    assert payload["current_state"] == "Executing"
    assert payload["current_task"] == "t1"


def test_validate_rejects_invalid_state(tmp_path: Path):
    cycle_dir, _ = _setup_validate_session(tmp_path)
    ws_path = cycle_dir / "tech" / "code" / "s1" / "workflow-state.md"
    save_workflow_state(ws_path, {"current_state": "Closing", "current_task": "", "current_phase": ""})
    with pytest.raises(ValueError, match="requires Preparing"):
        validate_preparing_to_executing(cycle_dir)


def test_validate_rejects_starting_state(tmp_path: Path):
    cycle_dir, _ = _setup_validate_session(tmp_path)
    ws_path = cycle_dir / "tech" / "code" / "s1" / "workflow-state.md"
    save_workflow_state(ws_path, {"current_state": "Starting", "current_task": "", "current_phase": ""})
    with pytest.raises(ValueError, match="requires Preparing"):
        validate_preparing_to_executing(cycle_dir)


def test_validate_cli(tmp_path: Path):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    subprocess.run(["git", "init"], cwd=worktree, capture_output=True, check=True)
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "--project-root",
            str(tmp_path),
            "--validate",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["current_task"] == "t1"
    assert payload["current_state"] == "Executing"
    assert payload["slug"] == "wt"
    assert payload["branch"] == "wt/feat-slug-1"


def test_main_default_path_stdout(monkeypatch, tmp_path: Path, capsys):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    prepare_called = []

    def _fake_prepare(project_root, workspace):
        prepare_called.append((project_root, workspace))
        wt_path = Path(workspace["worktree_path"].rstrip("/"))
        wt_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=wt_path, capture_output=True, check=True)

    monkeypatch.setattr("tc_prepare.prepare_worktrees", _fake_prepare)
    monkeypatch.setattr(
        "tc_git_ops.is_worktree",
        lambda path: Path(normalize_repo_path(path)).joinpath(".git").exists(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tc_prepare.py",
            "--cycle-dir",
            str(cycle_dir),
            "--project-root",
            str(tmp_path),
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["current_state"] == "Executing"
    assert payload["current_task"] == "t1"
    assert payload["worktree_path"].startswith(str(tmp_path.resolve()))
    assert payload["slug"]
    assert payload["branch"].startswith("wt/feat-")
    assert len(prepare_called) == 1


def _git_cfg() -> dict:
    return {
        "worktree_base": ".cache/worktrees",
        "branch_pattern": "wt/{type}-{slug}",
        "default_type": "feat",
    }


def _minimal_tasks():
    return [{"task_id": "t1", "target_repo": "repo-a", "execution_worktree": "feature_worktree"}]


def test_ensure_workspace_first_create(tmp_path: Path):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    dest, workspace, slug, branch, created = ensure_workspace(
        cycle_dir, 1, "cycle-id", _minimal_tasks(), tmp_path, _git_cfg()
    )
    assert created is True
    assert dest.exists()
    assert workspace["branch"] == branch
    assert slug in workspace["worktree_path"]


def test_ensure_workspace_reuses_valid_file(tmp_path: Path, monkeypatch):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    dest, workspace, slug, branch, created = ensure_workspace(
        cycle_dir, 1, "cycle-id", _minimal_tasks(), tmp_path, _git_cfg()
    )
    assert created is True
    created_at = workspace["created_at"]
    mtime = dest.stat().st_mtime

    monkeypatch.setattr("tc_prepare._derive_slug", lambda _cid: "should-not-be-used")

    dest2, workspace2, slug2, branch2, created2 = ensure_workspace(
        cycle_dir, 1, "cycle-id", _minimal_tasks(), tmp_path, _git_cfg()
    )
    assert created2 is False
    assert dest2 == dest
    assert workspace2["created_at"] == created_at
    assert slug2 == slug
    assert branch2 == branch
    assert dest.stat().st_mtime == mtime


def test_ensure_workspace_recreates_invalid_json(tmp_path: Path, monkeypatch):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    ws_path = cycle_dir / "tech" / "code" / "s1" / "workspace.json"
    ws_path.write_text("{bad json", encoding="utf-8")

    fixed_slug = "fixed-slug-abcd"
    monkeypatch.setattr("tc_prepare._derive_slug", lambda _cid: fixed_slug)

    dest, workspace, slug, branch, created = ensure_workspace(
        cycle_dir, 1, "cycle-id", _minimal_tasks(), tmp_path, _git_cfg()
    )
    assert created is True
    assert slug == fixed_slug
    assert fixed_slug in workspace["worktree_path"]
    assert branch == f"wt/feat-{fixed_slug}"


def test_ensure_workspace_recreates_missing_field(tmp_path: Path, monkeypatch):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    ws_path = cycle_dir / "tech" / "code" / "s1" / "workspace.json"
    ws_path.write_text(json.dumps({"worktree_path": "/x/"}), encoding="utf-8")

    fixed_slug = "new-slug-efgh"
    monkeypatch.setattr("tc_prepare._derive_slug", lambda _cid: fixed_slug)

    dest, workspace, slug, _, created = ensure_workspace(
        cycle_dir, 1, "cycle-id", _minimal_tasks(), tmp_path, _git_cfg()
    )
    assert created is True
    assert slug == fixed_slug
    assert "created_at" in workspace


def test_main_preserves_executing_current_task(tmp_path: Path, monkeypatch, capsys):
    cycle_dir, _ = _setup_full_preparing_session(tmp_path)
    session_dir = cycle_dir / "tech" / "code" / "s1"

    paths = build_worktree_paths("existing-slug", _git_cfg())
    write_workspace(
        cycle_dir, 1, "existing-slug", paths, _minimal_tasks(), tmp_path
    )
    created_at = json.loads(
        (session_dir / "workspace.json").read_text(encoding="utf-8")
    )["created_at"]

    save_workflow_state(
        session_dir / "workflow-state.md",
        {"current_state": "Executing", "current_task": "t3", "current_phase": ""},
    )
    (session_dir / "code-task-list.md").write_text(
        "- [x] t1 · done\n- [ ] t3 · task\n", encoding="utf-8"
    )

    def _fake_prepare(project_root, workspace):
        wt_path = Path(workspace["worktree_path"].rstrip("/"))
        wt_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=wt_path, capture_output=True, check=True)

    monkeypatch.setattr("tc_prepare.prepare_worktrees", _fake_prepare)
    monkeypatch.setattr(
        "tc_git_ops.is_worktree",
        lambda path: Path(normalize_repo_path(path)).joinpath(".git").exists(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tc_prepare.py",
            "--cycle-dir",
            str(cycle_dir),
            "--project-root",
            str(tmp_path),
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["current_task"] == "t3"
    assert payload["current_state"] == "Executing"
    after = json.loads((session_dir / "workspace.json").read_text(encoding="utf-8"))
    assert after["created_at"] == created_at
