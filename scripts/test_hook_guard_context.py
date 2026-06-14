#!/usr/bin/env python3
"""Tests for hook_guard.py conversation-indexed stage routing."""

import io
import json
import sys
from pathlib import Path
from typing import Optional

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_FID_A = "20260601135820-155a71e7"
_FID_B = "20260601141338-3764ab2b"
_CYCLE_ID = "feature-20260607084939-test0001"


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache/cursor/lulu-dev-workflow"


def _make_workflow_state(
    cache_dir: Path,
    cycle_id: str,
    stage: str,
    state: str,
    revision: str = "r1",
) -> None:
    import re

    from hook_guard import _STAGE_FLAT, _stage_subdir

    subdir = _stage_subdir(stage)
    if stage in _STAGE_FLAT:
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
        from hook_guard import _read_active_stage

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(tmp_path, "cursor", "conv-a", _FID_A, "tech-plan")
        active_context_schema.write_entry(tmp_path, "cursor", "conv-b", _FID_B, "product-plan")

        assert _read_active_stage("cursor", "conv-a") == "tech-plan"
        assert _read_active_stage("cursor", "conv-b") == "product-plan"

    def test_empty_conversation_id_returns_none(self, tmp_path, monkeypatch):
        from hook_guard import _read_active_stage

        monkeypatch.chdir(tmp_path)
        assert _read_active_stage("cursor", "") is None

    def test_unknown_conversation_returns_none(self, tmp_path, monkeypatch):
        from hook_guard import _read_active_stage

        monkeypatch.chdir(tmp_path)
        assert _read_active_stage("cursor", "missing") is None

    def test_legacy_flat_file_returns_none(self, tmp_path, monkeypatch):
        from hook_guard import _read_active_stage

        monkeypatch.chdir(tmp_path)
        ctx = tmp_path / ".cache/cursor/lulu-dev-workflow/active-context.json"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text(
            json.dumps({"cycle_id": _FID_A, "stage": "tech-plan"}),
            encoding="utf-8",
        )
        assert _read_active_stage("cursor", "conv-a") is None


class TestShouldInjectConversationId:
    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py --cycle-id fid1",
            "python3 ~/.cursor/skills/lulu-dev-workflow/scripts/hook_guard.py",
            "python lulu-dev-workflow/product-plan/scripts/start.py --project-root /tmp",
        ],
    )
    def test_workflow_py_invocation(self, command):
        from hook_guard import _should_inject_conversation_id

        assert _should_inject_conversation_id(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "docs(lulu-dev-workflow): subject"',
            "git diff lulu-dev-workflow/SKILL.md",
            "git add lulu-dev-workflow/scripts/hook_guard.py",
            "git status",
            "python3 cycle_control.py --project-root /tmp start --name test",
        ],
    )
    def test_non_workflow_py_invocation(self, command):
        from hook_guard import _should_inject_conversation_id

        assert _should_inject_conversation_id(command) is False

    def test_already_has_conv_id(self):
        from hook_guard import _should_inject_conversation_id

        cmd = "python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py --conversation-id existing"
        assert _should_inject_conversation_id(cmd) is False


class TestMainRouting:
    def test_no_conversation_id_allows(self, tmp_path, monkeypatch):
        import hook_guard

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
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"

    def test_unknown_conversation_id_allows(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        payload = _write_payload(conversation_id="unknown-conv")

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_legacy_file_allows(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        ctx = tmp_path / ".cache/cursor/lulu-dev-workflow/active-context.json"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text(
            json.dumps({"cycle_id": _FID_A, "stage": "tech-plan"}),
            encoding="utf-8",
        )

        payload = _write_payload(conversation_id="conv-a")
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        assert json.loads(captured.getvalue())["permission"] == "allow"

    def test_shell_non_workflow_command_allows(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": "git status"},
            "conversation_id": "conv-a",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_shell_workflow_command_injects_conv_id(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py --cycle-id fid1 --project-root /tmp"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
            "conversation_id": "conv-xyz",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert result["updated_input"]["command"].endswith("--conversation-id conv-xyz")

    def test_shell_already_has_conv_id_no_duplicate(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py --conversation-id existing"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
            "conversation_id": "conv-xyz",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_shell_workflow_command_no_conv_id_allows(self, tmp_path, monkeypatch):
        import hook_guard

        monkeypatch.chdir(tmp_path)
        cmd = "python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py --cycle-id fid1"
        payload = json.dumps({
            "tool_name": "Shell",
            "tool_input": {"command": cmd},
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
        assert "updated_input" not in result

    def test_routes_by_conversation_id(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_guard

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(tmp_path, "cursor", "conv-a", _FID_A, "tech-plan")
        active_context_schema.write_entry(tmp_path, "cursor", "conv-b", _FID_B, "product-plan")

        loaded: list[str] = []

        def fake_load_stage(stage: str):
            loaded.append(stage)

            class _Mod:
                @staticmethod
                def main() -> int:
                    print(json.dumps({"permission": "allow", "routed_stage": stage}))
                    return 0

            return _Mod()

        monkeypatch.setattr(hook_guard, "_load_stage_module", fake_load_stage)

        for conv_id, expected_stage in (("conv-a", "tech-plan"), ("conv-b", "product-plan")):
            loaded.clear()
            payload = _write_payload(conversation_id=conv_id)
            monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
            captured = io.StringIO()
            monkeypatch.setattr(sys, "stdout", captured)
            assert hook_guard.main() == 0
            assert loaded == [expected_stage]
            result = json.loads(captured.getvalue())
            assert result["permission"] == "allow"
            assert result["routed_stage"] == expected_stage


class TestDeliveredBypass:
    def test_delivered_allows_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_guard

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "tech-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "tech-plan", "Delivered")

        loaded: list[str] = []

        def fake_load_stage(stage: str):
            loaded.append(stage)
            raise AssertionError("stage module should not load when Delivered")

        monkeypatch.setattr(hook_guard, "_load_stage_module", fake_load_stage)

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        assert loaded == []
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"

    def test_not_delivered_denies_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_guard

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "tech-plan"
        )
        _make_workflow_state(_cache_dir(tmp_path), _CYCLE_ID, "tech-plan", "Drafting")

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"
        assert "[lulu-dev-workflow]" in result["user_message"]
        assert "STOP" in result["agent_message"]
        assert "inform the user" in result["agent_message"].lower()

    def test_invalidated_still_denies_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_guard

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "tech-plan"
        )
        _make_workflow_state(
            _cache_dir(tmp_path), _CYCLE_ID, "tech-plan", "Invalidated"
        )

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        result = json.loads(captured.getvalue())
        assert result["permission"] == "deny"

    def test_flat_stage_delivered_allows_outside_cache(self, tmp_path, monkeypatch):
        import active_context_schema
        import hook_guard

        monkeypatch.chdir(tmp_path)
        active_context_schema.write_entry(
            tmp_path, "cursor", "conv-a", _CYCLE_ID, "diagnostic"
        )
        _make_workflow_state(
            _cache_dir(tmp_path), _CYCLE_ID, "diagnostic", "Delivered"
        )

        loaded: list[str] = []

        def fake_load_stage(stage: str):
            loaded.append(stage)
            raise AssertionError("stage module should not load when Delivered")

        monkeypatch.setattr(hook_guard, "_load_stage_module", fake_load_stage)

        payload = _write_payload(
            conversation_id="conv-a",
            file_path=str(tmp_path / "src" / "main.py"),
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        assert hook_guard.main() == 0
        assert loaded == []
        result = json.loads(captured.getvalue())
        assert result["permission"] == "allow"
