"""Tests for exec-stage rename aliases and cache migration."""

from pathlib import Path

from stage_identity import (
    EXEC_STAGE,
    EXEC_STAGE_LEGACY,
    exec_stage_dir,
    migrate_exec_stage_dir,
    resolve_stage_cache_dir,
    stage_config_aliases,
)


def test_aliases_prefer_modern_name():
    assert stage_config_aliases(EXEC_STAGE) == (EXEC_STAGE, EXEC_STAGE_LEGACY)
    assert stage_config_aliases(EXEC_STAGE_LEGACY) == (EXEC_STAGE, EXEC_STAGE_LEGACY)
    assert stage_config_aliases("lulu-tasks") == ("lulu-tasks",)


def test_exec_stage_dir_reads_legacy(tmp_path: Path):
    cycle = tmp_path / "cycle"
    legacy = cycle / EXEC_STAGE_LEGACY
    legacy.mkdir(parents=True)
    (legacy / "session-state.md").write_text("ok\n", encoding="utf-8")
    found = exec_stage_dir(cycle)
    assert found == legacy
    assert (found / "session-state.md").read_text(encoding="utf-8") == "ok\n"


def test_exec_stage_dir_prefers_modern(tmp_path: Path):
    cycle = tmp_path / "cycle"
    modern = cycle / EXEC_STAGE
    legacy = cycle / EXEC_STAGE_LEGACY
    modern.mkdir(parents=True)
    legacy.mkdir(parents=True)
    assert exec_stage_dir(cycle) == modern


def test_migrate_renames_legacy_when_modern_absent(tmp_path: Path):
    cycle = tmp_path / "cycle"
    legacy = cycle / EXEC_STAGE_LEGACY / "s1"
    legacy.mkdir(parents=True)
    (legacy / "marker").write_text("keep\n", encoding="utf-8")
    dest = migrate_exec_stage_dir(cycle)
    assert dest == cycle / EXEC_STAGE
    assert not (cycle / EXEC_STAGE_LEGACY).exists()
    assert (dest / "s1" / "marker").read_text(encoding="utf-8") == "keep\n"


def test_migrate_rewrites_workflow_state_cache_paths(tmp_path: Path):
    cycle = tmp_path / "cycle"
    ws = cycle / EXEC_STAGE_LEGACY / "s1" / "workflow-state.md"
    ws.parent.mkdir(parents=True)
    ws.write_text(
        f"task_list_ref: /tmp/x/{EXEC_STAGE_LEGACY}/s1/code-task-list.md\n",
        encoding="utf-8",
    )
    dest = migrate_exec_stage_dir(cycle)
    text = (dest / "s1" / "workflow-state.md").read_text(encoding="utf-8")
    assert f"/{EXEC_STAGE}/s1/code-task-list.md" in text
    assert f"/{EXEC_STAGE_LEGACY}/" not in text


def test_resolve_stage_cache_dir_aliases_exec(tmp_path: Path):
    cycle_id = "feat-1"
    legacy = tmp_path / cycle_id / EXEC_STAGE_LEGACY
    legacy.mkdir(parents=True)
    assert resolve_stage_cache_dir(tmp_path, cycle_id, EXEC_STAGE) == legacy
    assert resolve_stage_cache_dir(tmp_path, cycle_id, EXEC_STAGE_LEGACY) == legacy
