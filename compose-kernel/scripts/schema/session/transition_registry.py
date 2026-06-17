"""Load shared compose session transition table (compose-session.json)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

_CORE = Path(__file__).resolve().parents[2] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_common import WHITELIST_PATH  # noqa: E402

_table_cache: Optional[dict] = None
_states_cache: Optional[frozenset[str]] = None


def load_transition_table(path: Optional[Path] = None) -> dict:
    """Return parsed session transition table JSON."""
    global _table_cache
    resolved = path or WHITELIST_PATH
    if path is None and _table_cache is not None:
        return _table_cache
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if path is None:
        _table_cache = data
    return data


def session_states(path: Optional[Path] = None) -> frozenset[str]:
    """Return allowed workflow-state current_state values."""
    global _states_cache
    if path is None and _states_cache is not None:
        return _states_cache
    data = load_transition_table(path)
    declared = data.get("states")
    if isinstance(declared, list) and declared:
        states = frozenset(str(s) for s in declared)
    else:
        states = set()
        for entry in data.get("transitions", []):
            if entry.get("from"):
                states.add(str(entry["from"]))
            if entry.get("to"):
                states.add(str(entry["to"]))
        states = frozenset(states)
    if path is None:
        _states_cache = states
    return states


def is_allowed(command: str, from_state: str, to_state: str, path: Optional[Path] = None) -> bool:
    """Return True if command may transition from_state -> to_state."""
    for entry in load_transition_table(path).get("transitions", []):
        if entry.get("from") != from_state or entry.get("to") != to_state:
            continue
        entry_command = entry.get("command")
        if entry_command is None or entry_command == command:
            return True
    return False
