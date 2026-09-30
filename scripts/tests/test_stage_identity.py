"""Tests for exec-stage identity and cache paths."""

from pathlib import Path

from stage_identity import EXEC_STAGE, exec_stage_dir, resolve_stage_cache_dir


def test_exec_stage_name():
    assert EXEC_STAGE == "lulu-exec"


def test_exec_stage_dir(tmp_path: Path):
    cycle = tmp_path / "cycle"
    assert exec_stage_dir(cycle) == cycle / EXEC_STAGE


def test_resolve_stage_cache_dir(tmp_path: Path):
    cycle_id = "feat-1"
    assert resolve_stage_cache_dir(tmp_path, cycle_id, EXEC_STAGE) == (
        tmp_path / cycle_id / EXEC_STAGE
    )
    assert resolve_stage_cache_dir(tmp_path, cycle_id, "lulu-tasks") == (
        tmp_path / cycle_id / "lulu-tasks"
    )
