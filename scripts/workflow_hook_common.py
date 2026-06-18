"""Shared agent STOP messaging and helpers for workflow enforcement."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_HOOK_COMMON = _SCRIPTS / "hook" / "workflow_hook_common.py"


def _load_hook_common():
    name = "lulu_hook_workflow_common"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _HOOK_COMMON)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_hook_common = _load_hook_common()

agent_stop_message = _hook_common.agent_stop_message
deny_rw_boundary = _hook_common.deny_rw_boundary
deny_cache_boundary = _hook_common.deny_cache_boundary

__all__ = ["agent_stop_message", "deny_cache_boundary", "deny_rw_boundary"]
