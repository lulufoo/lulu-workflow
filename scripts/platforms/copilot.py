"""Copilot platform adapter: normalize camelCase payload to Cursor format."""

TOOL_NAME_MAP = {
    "create_file": "Write",
    "replace_string_in_file": "Edit",
    "multi_replace_string_in_file": "Edit",
}


def normalize(payload: dict) -> dict:
    """Map Copilot camelCase fields to Cursor snake_case equivalents."""
    tool_name_raw = payload.get("toolName") or payload.get("tool_name") or ""
    tool_name = TOOL_NAME_MAP.get(tool_name_raw, tool_name_raw)

    tool_input_raw = payload.get("toolInput") or payload.get("tool_input") or {}
    tool_input = dict(tool_input_raw)

    # multi_replace_string_in_file: use first replacement's filePath
    if tool_name_raw == "multi_replace_string_in_file":
        replacements = tool_input.get("replacements") or []
        first_path = replacements[0].get("filePath", "") if replacements else ""
        tool_input = {"file_path": first_path}
    elif "filePath" in tool_input:
        tool_input["file_path"] = tool_input.pop("filePath")

    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "conversation_id": payload.get("sessionId") or payload.get("conversation_id") or "",
    }
