#!/usr/bin/env python3
"""Tests for scripts/hook/hook_guard.py conversation-indexed stage routing."""

import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Optional

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SKILL_ROOT = _SCRIPTS.parent
_HOOK_ENTRY = _SCRIPTS / "hook" / "hook_guard.py"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "hook") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS / "hook"))


def _load_hook_entry():
    name = "lulu_hook_entry"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _HOOK_ENTRY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


hook_entry = _load_hook_entry()

_FID_A = "20260601135820-155a71e7"
_FID_B = "20260601141338-3764ab2b"
_CYCLE_ID = "feature-20260607084939-test0001"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache/cursor/lulu-workflow"


def _make_workflow_state(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    state: str,
    revision: str = "r1",
) -> None:
    import re

    from workflow_sessions import STAGE_FLAT, stage_subdir

    subdir = stage_subdir(stage)
    if stage in STAGE_FLAT:
        session_dir = cache_dir / cycle_id / subdir
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "session-state.md"
    else:
        rev_name = (
            f"revision{revision.lstrip('r')}"
            if re.match(r"^r\d+$", revision)
            else revision
        )
        session_dir = cache_dir / cycle_id / subdir / rev_name
        session_dir.mkdir(parents=True, exist_ok=True)
        ws = session_dir / "workflow-state.md"
    ws.write_text(
        f"---\ncurrent_state: {state}\nupdated_at: 2026-06-07T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _write_payload(
    *,
    conversation_id: Optional[str] = "conv-a",
    tool_name: str = "Write",
    file_path: str = "/tmp/outside-cache.txt",
) -> str:
    payload = {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    return json.dumps(payload)


class TestReadActiveStage:
    def test_returns_stage_for_conversation(self, tmp_path, monkeypatch):
        import active_context_schema

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(tmp_path, "cursor", "conv-a", _FID_A, "lulu-plan")
        active_context_schema.write_entry(
            tmp_path,
            "cursor",
            "conv-b",
            _FID_B,
            "lulu-blueprint",
            cycle_type="topic",
        )

        assert hook_entry._read_active_stage("cursor", "conv-a") == "lulu-plan"
        assert hook_entry._read_active_stage("cursor", "conv-b") == "lulu-blueprint"

    def test_empty_conversation_id_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert hook_entry._read_active_stage("cursor", "") is None

    def test_unknown_conversation_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert hook_entry._read_active_stage("cursor", "missing") is None

    def test_legacy_flat_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ctx = tmp_path / ".cache/cursor/lulu-workflow/active-context.json"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text(
            json.dumps({"cycle_id": _FID_A, "stage": "lulu-plan"}),
            encoding="utf-8",
        )
        assert hook_entry._read_active_stage("cursor", "conv-a") is None


class TestShouldInjectConversationId:
    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.cursor/skills/lulu-workflow/decision/scripts/dec_start.py --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/runtime_control.py --project-root /tmp resolve-session-context",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/cycle_control.py --project-root /tmp bind-context --cycle-id fid1 --skill-dir /tmp/lulu-plan",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/start.py --profile lulu-blueprint --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/start.py --profile lulu-spec --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/start.py --profile lulu-plan --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/start.py --profile lulu-design --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/lulu-tasks/scripts/tt_start.py --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/lulu-exec/scripts/tc_start.py --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/lulu-exec/scripts/tc_task_control.py resolve-context --task-id t1",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/inductive/inductive_gate_control.py init-session --out-dir /tmp/r1",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/inductive/recompose/inductive_recompose_control.py record-recompose-report --out-dir /tmp/r1 --json '{}'",
        ],
    )
    def test_start_py_invocation(self, command):
        assert hook_entry._should_inject_conversation_id(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "docs(lulu-workflow): subject"',
            "git diff lulu-workflow/SKILL.md",
            "git add lulu-workflow/scripts/hook/hook_guard.py",
            "git status",
            "python3 cycle_control.py --project-root /tmp start --name test",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/hook/hook_guard.py",
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/l_step_control.py --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/cycle_control.py start --name test",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/cycle_control.py resolve-token --token F1",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/cycle_control.py menu",
            "python3 ~/.cursor/skills/lulu-workflow/scripts/runtime_control.py --project-root /tmp resolve-platform-context",
        ],
    )
    def test_non_workflow_py_invocation(self, command):
        assert hook_entry._should_inject_conversation_id(command) is False

    def test_already_has_conv_id(self):
        cmd = "python3 ~/.cursor/skills/lulu-workflow/decision/scripts/dec_start.py --conversation-id existing"
        assert hook_entry._should_inject_conversation_id(cmd) is False

    def test_inductive_override_replaces_agent_conv_id(self):
        cmd = (
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/inductive/"
            "inductive_gate_control.py init-session --out-dir /tmp/r1 "
            '--conversation-id "feature-20260703084622-3b3a7fdd-lulu-design"'
        )
        updated = hook_entry._apply_conversation_id(cmd, "9001dc22-85f1-404b-869c-2e471433da4d")
        assert updated is not None
        assert "9001dc22-85f1-404b-869c-2e471433da4d" in updated
        assert "feature-20260703084622-3b3a7fdd-lulu-design" not in updated

    def test_inductive_injects_when_flag_absent(self):
        cmd = (
            "python3 ~/.cursor/skills/lulu-workflow/compose/scripts/inductive/"
            "recompose/inductive_recompose_control.py record-recompose-report --out-dir /tmp/r1 --json '{}'"
        )
        updated = hook_entry._apply_conversation_id(cmd, "9001dc22-85f1-404b-869c-2e471433da4d")
        assert updated is not None
        assert updated.endswith("--conversation-id 9001dc22-85f1-404b-869c-2e471433da4d")

    def test_multiline_command_injects_only_matching_line(self):
        """Regression: a multi-line Shell call mixing inductive_gate_control.py
        (injectable) with l_step_control.py (not injectable — no
        --conversation-id flag) must not append the flag to the whole blob's
        tail. Previously this produced a bare trailing "--conversation-id <id>"
        line that zsh ran as its own (failing) command.
        """
        cmd = (
            'OUT="/tmp/r1"\n'
            'python3 ~/.cursor/skills/lulu-workflow/compose/scripts/inductive/'
            'inductive_gate_control.py --out-dir "$OUT" gate-close --gate G3\n'
            'python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/'
            'l_step_control.py --cycle-id fid1 enter-deductive 2>&1\n'
        )
        updated = hook_entry._apply_conversation_id(cmd, "9001dc22-85f1-404b-869c-2e471433da4d")
        assert updated is not None
        lines = updated.split("\n")
        assert lines[0] == 'OUT="/tmp/r1"'
        assert lines[1].endswith(
            "gate-close --gate G3 --conversation-id 9001dc22-85f1-404b-869c-2e471433da4d"
        )
        # The l_step_control line has no flag registered — must be left untouched.
        assert lines[2].endswith("enter-deductive 2>&1")
        assert "--conversation-id" not in lines[2]
        # No stray trailing statement — never a bare "--conversation-id ..." line.
        assert lines[3] == ""

    def test_multiline_command_no_injectable_line_returns_none(self):
        cmd = (
            'OUT="/tmp/r1"\n'
            'python3 ~/.cursor/skills/lulu-workflow/compose/scripts/session/'
            'l_step_control.py --cycle-id fid1 enter-deductive 2>&1\n'
        )
        assert hook_entry._apply_conversation_id(cmd, "9001dc22-85f1-404b-869c-2e471433da4d") is None

    def test_single_line_chain_injects_target_segment_only(self):
        cmd = (
            'python3 ~/.cursor/skills/lulu-workflow/scripts/runtime_control.py '
            '--project-root /tmp resolve-platform-context && '
            'python3 ~/.cursor/skills/lulu-workflow/scripts/runtime_control.py '
            '--project-root /tmp resolve-session-context && '
            'cat /tmp/demo.json'
        )
        updated = hook_entry._apply_conversation_id(cmd, "conv-xyz")
        assert updated is not None
        assert (
            "resolve-session-context --conversation-id conv-xyz && cat /tmp/demo.json"
            in updated
        )
        assert "cat /tmp/demo.json --conversation-id conv-xyz" not in updated

    def test_single_line_semicolon_chain_injects_target_segment_only(self):
        cmd = (
            'python3 ~/.cursor/skills/lulu-workflow/scripts/runtime_control.py '
            '--project-root /tmp resolve-session-context; '
            'echo done'
        )
        updated = hook_entry._apply_conversation_id(cmd, "conv-xyz")
        assert updated is not None
        assert "resolve-session-context --conversation-id conv-xyz; echo done" in updated
        assert "echo done --conversation-id conv-xyz" not in updated

    @pytest.mark.parametrize(
        "command",
        [
            'python3 "$SKILL_ROOT/scripts/runtime_control.py" --project-root /tmp resolve-session-context',
            'python3 "${SKILL_ROOT}/scripts/runtime_control.py" --project-root /tmp resolve-session-context',
            'python3 "$SKILL_DIR/scripts/tt_start.py" --cycle-id fid1',
            'python3 "${SKILL_DIR}/scripts/dec_start.py" --cycle-id fid1',
            'python3 "$DECISION_SKILL_DIR/scripts/dec_start.py" --cycle-id fid1',
            'python3 "${DECISION_SKILL_DIR}/scripts/dec_start.py" --cycle-id fid1',
            'python3 "$SKILL_DIR/scripts/tc_start.py" --cycle-id fid1',
            'python3 "$SKILL_ROOT/compose/scripts/session/start.py" --profile lulu-plan --cycle-id fid1',
        ],
    )
    def test_skill_var_path_injects(self, command):
        assert hook_entry._should_inject_conversation_id(command) is True

    def test_skill_root_resolve_platform_context_does_not_inject(self):
        cmd = (
            'python3 "$SKILL_ROOT/scripts/runtime_control.py" '
            "--project-root /tmp resolve-platform-context"
        )
        assert hook_entry._should_inject_conversation_id(cmd) is False

    def test_skill_root_chain_injects_resolve_session_segment(self):
        cmd = (
            'python3 "$SKILL_ROOT/scripts/runtime_control.py" '
            "--project-root /tmp resolve-platform-context && "
            'python3 "$SKILL_ROOT/scripts/runtime_control.py" '
            "--project-root /tmp resolve-session-context && "
            "cat /tmp/demo.json"
        )
        updated = hook_entry._apply_conversation_id(cmd, "conv-xyz")
        assert updated is not None
        assert (
            "resolve-session-context --conversation-id conv-xyz && cat /tmp/demo.json"
            in updated
        )
        assert "cat /tmp/demo.json --conversation-id conv-xyz" not in updated

    def test_skill_root_inductive_override(self):
        cmd = (
            'python3 "$SKILL_ROOT/compose/scripts/inductive/'
            'inductive_gate_control.py" init-session --out-dir /tmp/r1 '
            '--conversation-id "wrong-id"'
        )
        updated = hook_entry._apply_conversation_id(cmd, "9001dc22-85f1-404b-869c-2e471433da4d")
        assert updated is not None
        assert "9001dc22-85f1-404b-869c-2e471433da4d" in updated
        assert "wrong-id" not in updated


class TestMainRouting:
    def test_no_conversation_id_allows(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/outside-cache.txt"},
            }
        )

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"

    def test_unknown_conversation_id_allows(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        payload = _write_payload(conversation_id="unknown-conv")

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_legacy_file_allows(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ctx = tmp_path / ".cache/cursor/lulu-workflow/active-context.json"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text(
            json.dumps({"cycle_id": _FID_A, "stage": "lulu-plan"}),
            encoding="utf-8",
        )

        payload = _write_payload(conversation_id="conv-a")
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_shell_non_workflow_command_allows(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": "git status"},
            "conversation_id": "conv-a",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_shell_workflow_command_injects_conv_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-workflow/decision/scripts/dec_start.py --cycle-id fid1 --project-root /tmp"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
            "conversation_id": "conv-xyz",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert result["updated_input"]["command"].endswith("--conversation-id conv-xyz")

    def test_shell_already_has_conv_id_no_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-workflow/decision/scripts/dec_start.py --conversation-id existing"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
            "conversation_id": "conv-xyz",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_shell_workflow_command_no_conv_id_allows(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-workflow/decision/scripts/dec_start.py --cycle-id fid1"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_write_inside_cache_allows(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")
        cache_file = (
            _cache_dir(tmp_path) / _CYCLE_ID / "lulu-plan/revision1/note.md"
        )
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        payload = _write_payload(conversation_id="conv-a", file_path=str(cache_file))
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"


class TestDeliveredBypass:
    def test_delivered_allows_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Delivered")

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"

    def test_not_delivered_denies_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"
        assert "[lulu-workflow]" in result["user_message"]
        assert "STOP" in result["agent_message"]
        assert "report this message to the user" in result["agent_message"].lower()

    def test_invalidated_still_denies_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(
            _cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Invalidated"
        )

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"

    def test_flat_stage_delivered_allows_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "decision"
        )
        _make_workflow_state(
            _cache_dir(tmp_path), _CYCLE_ID, "decision", "Delivered"
        )

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"


class TestRwGuard:
    def test_tech_code_allows_project_write(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-exec"
        )
        target = tmp_path / "src" / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _write_payload(conversation_id="conv-a", file_path=str(target))
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_rw_guard_disabled_allows_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_config_schema

        monkeypatch.chdir(tmp_path)
        hook_config_schema.ensure_hook_config(tmp_path, platform="cursor")
        cfg_path = hook_config_schema.resolve_hook_config_path(tmp_path, "cursor")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["internalPathGuard"]["enable"] = False
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")
        target = tmp_path / "src" / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _write_payload(conversation_id="conv-a", file_path=str(target))
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_read_inside_project_allows(self, tmp_path, monkeypatch):
        import active_context_schema
        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")
        target = tmp_path / "README.md"
        target.write_text("hello", encoding="utf-8")
        payload = _write_payload(
            conversation_id="conv-a",
            tool_name="Read",
            file_path=str(target),
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_read_inside_platform_skills_allows(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_config_schema

        monkeypatch.chdir(tmp_path)
        hook_config_schema.ensure_hook_config(tmp_path, platform="cursor")
        cfg_path = hook_config_schema.resolve_hook_config_path(tmp_path, "cursor")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["externalPathGuard"] = {
            "enabled": True,
            "readAllowExternalPaths": ["~/.cursor/"],
            "writeAllowExternalPaths": [],
            "sessionAllow": False,
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")
        target = Path.home() / ".cursor/skills/other-skill/SKILL.md"
        payload = _write_payload(
            conversation_id="conv-a",
            tool_name="Read",
            file_path=str(target),
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_read_outside_project_denies(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_config_schema

        monkeypatch.chdir(tmp_path)
        hook_config_schema.ensure_hook_config(tmp_path, platform="cursor")
        cfg_path = hook_config_schema.resolve_hook_config_path(tmp_path, "cursor")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["externalPathGuard"] = {
            "enabled": True,
            "readAllowExternalPaths": ["~/.cursor/"],
            "writeAllowExternalPaths": [],
            "sessionAllow": False,
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Working")
        outside = Path("/tmp/lulu-hook-read-outside-test.md")
        payload = _write_payload(
            conversation_id="conv-a",
            tool_name="Read",
            file_path=str(outside),
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"
        assert "externalPathGuard" in result.get("agent_message", "")

    def test_no_stage_still_denies_external_when_enabled(self, tmp_path, monkeypatch):
        import hook_config_schema

        monkeypatch.chdir(tmp_path)
        hook_config_schema.ensure_hook_config(tmp_path, platform="cursor")
        cfg_path = hook_config_schema.resolve_hook_config_path(tmp_path, "cursor")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["externalPathGuard"] = {
            "enabled": True,
            "readAllowExternalPaths": [],
            "writeAllowExternalPaths": [],
            "sessionAllow": False,
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        payload = _write_payload(
            conversation_id="missing",
            tool_name="Read",
            file_path="/tmp/lulu-hook-no-stage-external.md",
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"

    def test_delivered_does_not_bypass_external_write(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_config_schema

        monkeypatch.chdir(tmp_path)
        hook_config_schema.ensure_hook_config(tmp_path, platform="cursor")
        cfg_path = hook_config_schema.resolve_hook_config_path(tmp_path, "cursor")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["externalPathGuard"] = {
            "enabled": True,
            "readAllowExternalPaths": [],
            "writeAllowExternalPaths": [],
            "sessionAllow": False,
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "lulu-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "lulu-plan", "Delivered")
        payload = _write_payload(
            conversation_id="conv-a",
            file_path="/tmp/lulu-hook-delivered-external.txt",
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"


class TestClaudePlatformOutput:
    def test_claude_write_outside_cache_denies_with_hook_specific_output(
        self, tmp_path, monkeypatch
    ):
        import active_context_schema

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys,
            "argv",
            ["hook_guard.py", "--platform", "claude"],
        )
        active_context_schema.write_entry(
            tmp_path, "claude", "sess-1", _CYCLE_ID, "lulu-plan"
        )
        cache = tmp_path / ".cache/claude/lulu-workflow"
        _make_workflow_state(cache, _CYCLE_ID, "lulu-plan", "Working")
        payload = json.dumps(
            {
                "session_id": "sess-1",
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "outside.md")},
            }
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_entry.main() == 0
        out = json.loads(captured.getvalue())
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
