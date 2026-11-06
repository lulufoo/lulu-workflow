"""Interaction contracts for the lulu-exec router and its loaded units."""

from __future__ import annotations

import re
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parents[2] / "lulu-exec"
_ENTRY = _SKILL_ROOT / "SKILL.md"
_EXECUTING = _SKILL_ROOT / "references" / "executing.md"
_PREPARING = _SKILL_ROOT / "references" / "preparing.md"
_CLOSING = _SKILL_ROOT / "references" / "closing.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_entry_uses_cycle_type_without_execution_mode_branching():
    content = _text(_ENTRY)
    assert "$EXECUTION_MODE" not in content
    assert "execution_mode:" not in content
    assert "## Execution Mode" not in content
    assert "### Autonomous Overrides" not in content


def test_feature_auto_resumes_and_topic_recovery_requires_confirmation():
    content = _text(_ENTRY)
    assert re.search(r"\$CYCLE_TYPE` is `topic`.*ask to resume", content)
    assert re.search(r"Feature containers? auto-resume", content)


def test_task_confirmation_follows_container_policy():
    content = _text(_EXECUTING)
    assert re.search(r"Feature container: on `TASK_COMPLETE`, run `\$TC_CONFIRM`", content)
    assert re.search(r"Topic container: wait for confirmation, then `\$TC_CONFIRM`", content)
    assert "`$TC_CONFIRM` | `$TC_FLOW confirm-task-ready --task-id {task_id}`" in content


def test_delivery_follows_container_policy():
    content = _text(_CLOSING)
    assert re.search(r"Feature container.*run `\$TC_DELIVER` without asking", content)
    assert re.search(r"Topic container.*wait for explicit confirmation, then `\$TC_DELIVER`", content)
    assert "`$TC_DELIVER` | `$TC_FLOW deliver`" in content


def test_router_loads_units_and_refreshes_context():
    content = _text(_ENTRY)
    assert "Load the unit named by `$CTX.unit`" in content
    for unit in ("preparing", "executing", "closing"):
        assert f"`{unit}` → `$SKILL_DIR/references/{unit}.md`" in content
        assert (_SKILL_ROOT / "references" / f"{unit}.md").is_file()
    assert "`delivered` → stop" in content
    assert "run `$TC_CTX` again and load the unit it names" in content


def test_executing_dispatches_from_pointer_and_passes_context():
    content = _text(_EXECUTING)
    assert "route only from `$TC_POINTER`" in content
    assert "Pin `current_task`, `kind`, and `subagent`" in content
    assert "Pass `subagent` as `model` when set" in content
    assert "`kind: coding` → `task-runner/SKILL.md`" in content
    assert "`kind: action` → `action-runner/SKILL.md`" in content
    assert "Input: `task_id` and the absolute cycle dir" in content
    assert content.index("`TASK_FAILED` → Blocking policy") < content.index("Run `$TC_ADVANCE`")


def test_preparing_binds_repositories_before_worktree_preparation():
    content = _text(_PREPARING)
    assert content.index("Run `$TC_LIST_REPOS`") < content.index("Run `$TC_PUT_REPOS`")
    assert content.index("Run `$TC_PUT_REPOS`") < content.index("Run `$TC_PREPARE`")
    assert "If a name has no candidate, ask" in content
    assert "Non-zero → Blocking policy" in content
