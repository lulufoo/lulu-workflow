"""Shared helpers for platform hook registration during init-project."""

from __future__ import annotations

from typing import Any


def strip_lulu_hook_entries(entries: list[Any]) -> list[Any]:
    """Remove lulu-workflow hook commands from a hook event list."""
    result: list[Any] = []
    for entry in entries:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        nested = entry.get("hooks")
        if isinstance(nested, list):
            kept = [
                item for item in nested
                if "lulu-workflow" not in (item.get("command") or "")
            ]
            if kept:
                result.append({**entry, "hooks": kept})
            continue
        if "lulu-workflow" not in (entry.get("command") or ""):
            result.append(entry)
    return result
