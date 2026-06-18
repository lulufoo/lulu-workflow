"""Claude Code platform adapter: normalize PreToolUse stdin and format stdout.

See: https://code.claude.com/docs/en/hooks#pretooluse
"""

from __future__ import annotations

from typing import Any, Optional

_BASH_TOOL = "Bash"
_SHELL_TOOL = "Shell"


def normalize(payload: dict) -> dict:
    """Map Claude Code PreToolUse payload to internal hook_guard format."""
    tool_name_raw = payload.get("tool_name") or payload.get("toolName") or ""
    tool_name = _SHELL_TOOL if tool_name_raw == _BASH_TOOL else str(tool_name_raw)

    tool_input_raw = payload.get("tool_input") or payload.get("toolInput") or {}
    tool_input = dict(tool_input_raw) if isinstance(tool_input_raw, dict) else {}

    conversation_id = (
        payload.get("session_id")
        or payload.get("sessionId")
        or payload.get("conversation_id")
        or payload.get("conversationId")
        or ""
    )

    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "conversation_id": str(conversation_id),
    }


def _pretooluse_output(
    *,
    permission_decision: str,
    reason: str = "",
    updated_input: Optional[dict[str, Any]] = None,
) -> dict:
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": permission_decision,
        }
    }
    if reason:
        output["hookSpecificOutput"]["permissionDecisionReason"] = reason
    if updated_input is not None:
        output["hookSpecificOutput"]["updatedInput"] = updated_input
    return output


def format_response(
    response: dict,
    *,
    tool_name: str = "",
    tool_input: Optional[dict[str, Any]] = None,
) -> dict:
    """Convert internal hook_guard response to Claude Code PreToolUse stdout JSON."""
    del tool_name
    permission = response.get("permission", "allow")
    original_input = dict(tool_input or {})

    if permission == "deny":
        reason = (
            response.get("agent_message")
            or response.get("user_message")
            or "Blocked by lulu-dev-workflow hook"
        )
        return _pretooluse_output(
            permission_decision="deny",
            reason=str(reason),
        )

    updated = response.get("updated_input")
    if isinstance(updated, dict) and updated:
        merged = {**original_input, **updated}
        return _pretooluse_output(
            permission_decision="allow",
            updated_input=merged,
        )

    return _pretooluse_output(permission_decision="allow")
