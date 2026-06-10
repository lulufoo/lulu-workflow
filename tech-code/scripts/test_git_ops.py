#!/usr/bin/env python3
"""Tests for git_ops.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from git_ops import (  # noqa: E402
    branch_exists,
    create_worktree,
    is_worktree,
    normalize_repo_path,
    pre_check_clean,
    prepare_worktrees,
    resolve_worktree_action,
    status_clean,
    sync_repo,
    validate_worktrees,
    validate_worktrees_clean,
    worktree_branch,
)

_SCRIPT = Path(__file__).resolve().parent / "git_ops.py"


def test_normalize_repo_path():
    assert normalize_repo_path("/foo/bar/") == "/foo/bar"
    assert normalize_repo_path("/foo/bar") == "/foo/bar"


def test_is_worktree_true(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd == ["git", "-C", "/wt", "rev-parse", "--is-inside-work-tree"]
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert is_worktree("/wt/") is True


def test_is_worktree_false(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "false\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert is_worktree("/not-a-repo") is False


def test_status_clean_true(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd == ["git", "-C", "/wt", "status", "--porcelain"]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert status_clean("/wt/") is True


def test_status_clean_false(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert status_clean("/wt") is False


def test_validate_worktrees_missing_path():
    with pytest.raises(ValueError, match="missing worktree_path"):
        validate_worktrees({})


def test_validate_worktrees_invalid_primary(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="primary worktree is not a git worktree"):
        validate_worktrees({"worktree_path": "/bad/"})


def test_validate_worktrees_invalid_extra(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        path = cmd[2]
        if path == "/primary":
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra worktree for 'repo-b' is not a git worktree"):
        validate_worktrees({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {"path": "/extra/"}},
        })


def test_validate_worktrees_extra_missing_path(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra_worktree for 'repo-b' missing path"):
        validate_worktrees({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {}},
        })


def test_validate_worktrees_success(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    validate_worktrees({
        "worktree_path": "/primary/",
        "extra_worktrees": {"repo-b": {"path": "/extra/"}},
    })


def test_validate_worktrees_clean_dirty_primary(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        if cmd[3] == "status":
            return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="primary worktree has uncommitted changes"):
        validate_worktrees_clean({"worktree_path": "/primary/"})


def test_validate_worktrees_clean_dirty_extra(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        path = cmd[2]
        if path == "/extra":
            return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra worktree for 'repo-b' has uncommitted changes"):
        validate_worktrees_clean({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {"path": "/extra/"}},
        })


def test_validate_worktrees_clean_success(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    validate_worktrees_clean({
        "worktree_path": "/primary/",
        "extra_worktrees": {"repo-b": {"path": "/extra/"}},
    })


def test_cli_help():
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "is-worktree" in result.stdout


def test_cli_is_worktree_success(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init"], cwd=wt, capture_output=True, check=True)
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "is-worktree", "--path", str(wt)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"ok": True}


def test_cli_is_worktree_failure(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "is-worktree", "--path", str(wt)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "check failed" in result.stderr


def test_pre_check_clean_passes(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd[3] == "status" and cmd[4] == "--porcelain"
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    pre_check_clean("/repo")


def test_pre_check_clean_dirty(monkeypatch):
    calls = []

    def _run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[4] == "--porcelain":
            return subprocess.CompletedProcess(cmd, 0, " M file\n", "")
        if cmd[4] == "--short":
            return subprocess.CompletedProcess(cmd, 0, " M file\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="uncommitted changes"):
        pre_check_clean("/repo")
    assert any(c[4] == "--short" for c in calls)


def test_worktree_branch(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "wt/feat-slug\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert worktree_branch("/wt/") == "wt/feat-slug"


def test_branch_exists_true(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert "show-ref" in cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert branch_exists("/repo", "wt/feat-x") is True


def test_branch_exists_false(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert branch_exists("/repo", "missing") is False


def test_resolve_worktree_action_skip(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        if cmd[3] == "rev-parse" and cmd[4] == "--is-inside-work-tree":
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd[3] == "rev-parse" and cmd[4] == "--abbrev-ref":
            return subprocess.CompletedProcess(cmd, 0, "wt/feat-slug\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert resolve_worktree_action("/repo", "/wt/", "wt/feat-slug") == "skip"


def test_resolve_worktree_action_branch_mismatch(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        if cmd[3] == "rev-parse" and cmd[4] == "--is-inside-work-tree":
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd[3] == "rev-parse" and cmd[4] == "--abbrev-ref":
            return subprocess.CompletedProcess(cmd, 0, "other-branch\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="expected"):
        resolve_worktree_action("/repo", "/wt/", "wt/feat-slug")


def test_resolve_worktree_action_dir_collision(tmp_path: Path, monkeypatch):
    collision = tmp_path / "collision"
    collision.mkdir()

    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="not a git worktree"):
        resolve_worktree_action("/repo", str(collision), "wt/feat-slug")


def test_resolve_worktree_action_orphan_branch(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        if len(cmd) >= 5 and cmd[3] == "show-ref":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="branch .* exists but worktree path is missing"):
        resolve_worktree_action("/repo", "/missing/wt/", "wt/feat-slug")


def test_resolve_worktree_action_create(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert resolve_worktree_action("/repo", "/new/wt/", "wt/feat-new") == "create"


def test_sync_repo_success(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd[3:6] == ["pull", "--rebase"]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    sync_repo("/repo")


def test_sync_repo_conflict_aborts(monkeypatch):
    calls = []

    def _run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[3:6] == ["pull", "--rebase"]:
            return subprocess.CompletedProcess(cmd, 1, "", "conflict")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="sync failed"):
        sync_repo("/repo")
    assert any(c[3:6] == ["rebase", "--abort"] for c in calls)


def test_create_worktree(monkeypatch, tmp_path: Path):
    captured = []

    def _run(cmd, capture_output=True, text=True, check=False):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    wt_path = tmp_path / "wt"
    create_worktree("/repo", str(wt_path) + "/", "wt/feat-x")
    assert captured[0][1:4] == ["-C", "/repo", "worktree"]
    assert captured[0][4] == "add"
    assert captured[0][5] == str(wt_path.resolve())
    assert captured[0][6:8] == ["-b", "wt/feat-x"]


def _workspace(primary="/primary/", branch="wt/feat-slug", extra=None):
    ws = {"worktree_path": primary, "branch": branch}
    if extra:
        ws["extra_worktrees"] = extra
    return ws


def test_prepare_worktrees_happy_path(monkeypatch, tmp_path: Path):
    calls = []

    def _run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[3:5] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[3:6] == ["pull", "--rebase"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[3:5] == ["worktree", "add"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    wt = tmp_path / "wt"
    prepare_worktrees("/repo", _workspace(str(wt) + "/"))
    assert any(c[3:5] == ["pull", "--rebase"] for c in calls)
    assert any(c[3:5] == ["worktree", "add"] for c in calls)


def test_prepare_worktrees_resume_all_skip(monkeypatch):
    calls = []

    def _run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[3:5] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[3] == "rev-parse" and cmd[4] == "--is-inside-work-tree":
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd[3] == "rev-parse" and cmd[4] == "--abbrev-ref":
            return subprocess.CompletedProcess(cmd, 0, "wt/feat-slug\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    prepare_worktrees("/repo", _workspace("/existing/"))
    assert not any(c[3:6] == ["pull", "--rebase"] for c in calls)
    assert not any(c[3:5] == ["worktree", "add"] for c in calls)


def test_prepare_worktrees_extra_worktrees(monkeypatch, tmp_path: Path):
    calls = []

    def _run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[3:5] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[3:6] == ["pull", "--rebase"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[3:5] == ["worktree", "add"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    primary = tmp_path / "primary"
    extra = tmp_path / "extra"
    prepare_worktrees(
        "/repo",
        _workspace(
            str(primary) + "/",
            extra={"repo-b": {"path": str(extra) + "/", "branch": "wt/feat-slug-repo-b"}},
        ),
    )
    add_paths = [c[5] for c in calls if c[3:5] == ["worktree", "add"]]
    assert str(primary.resolve()) in add_paths
    assert str(extra.resolve()) in add_paths
    pull_calls = [c for c in calls if c[3:6] == ["pull", "--rebase"]]
    assert len(pull_calls) == 1


def test_cli_prepare_worktrees_smoke(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True, check=True)
    (repo / "README").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, capture_output=True, check=True)
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=repo, capture_output=True, check=True)

    wt_path = repo / "new-wt"
    workspace_path = tmp_path / "workspace-smoke.json"
    workspace_path.write_text(
        json.dumps({
            "worktree_path": str(wt_path) + "/",
            "branch": "wt/feat-slug",
        }),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "prepare-worktrees",
            "--project-root",
            str(repo),
            "--workspace",
            str(workspace_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
    assert wt_path.joinpath(".git").exists()
