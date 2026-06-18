#!/usr/bin/env python3
"""Tests for platforms/hook/claude.py."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platforms.hook.loader import load_hook_adapter  # noqa: E402

claude = load_hook_adapter("claude")


class TestClaudeNormalize:
    def test_maps_bash_to_shell(self):
        result = claude.normalize(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python3 scripts/start.py"},
                "session_id": "sess-1",
            }
        )
        assert result["tool_name"] == "Shell"
        assert result["tool_input"]["command"] == "python3 scripts/start.py"
        assert result["conversation_id"] == "sess-1"

    def test_write_preserves_file_path(self):
        result = claude.normalize(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/a.md", "content": "x"},
                "session_id": "sess-2",
            }
        )
        assert result["tool_name"] == "Write"
        assert result["tool_input"]["file_path"] == "/tmp/a.md"

    def test_session_id_aliases(self):
        result = claude.normalize({"sessionId": "abc", "tool_name": "Read", "tool_input": {}})
        assert result["conversation_id"] == "abc"


class TestClaudeFormatResponse:
    def test_allow_uses_hook_specific_output(self):
        out = claude.format_response({"permission": "allow"})
        assert out == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    def test_deny_uses_agent_message_as_reason(self):
        out = claude.format_response(
            {
                "permission": "deny",
                "agent_message": "STOP: outside cache",
                "user_message": "写入被拦截",
            }
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == "STOP: outside cache"

    def test_updated_input_merges_with_original_bash_fields(self):
        out = claude.format_response(
            {
                "permission": "allow",
                "updated_input": {"command": "python3 start.py --conversation-id sess-1"},
            },
            tool_name="Shell",
            tool_input={"command": "python3 start.py", "timeout": 120000},
        )
        updated = out["hookSpecificOutput"]["updatedInput"]
        assert updated["command"] == "python3 start.py --conversation-id sess-1"
        assert updated["timeout"] == 120000
