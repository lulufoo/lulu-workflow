#!/usr/bin/env python3
"""Unified preToolUse entry point. Routes to the active stage's hook_guard."""

import argparse
import importlib.util
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from active_context_schema import get_entry
from cycle_schema import read_stage as read_cycle_state  # noqa: F401
from cycle_schema import write_stage as write_cycle_state  # noqa: F401

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _SKILL_ROOT / "config"

_VALID_STATES = frozenset({"Drafting", "Evaluating", "TDABlocked", "Delivered", "Invalidated"})

# Flat stages use session-state.md directly (no revision subdirectories).
_STAGE_FLAT = frozenset({"diagnostic", "product-diagnostic", "tech-diagnostic"})
_FLAT_VALID_STATES = frozenset({"InProgress", "Delivered", "Invalidated"})
_STAGE_REVISION_PAT = re.compile(r"^(revision|r|s)\d+$")


def _stage_subdir(stage: str) -> str:
    """Convert stage name to cache subdirectory: product-plan → product/plan."""
    return stage.replace("-", "/", 1)


# ---------------------------------------------------------------------------
# Gate model: data classes and helpers
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    revision: str              # "revision1", "revision2", ... or "r0" for flat stages
    state: str                 # Drafting / Evaluating / Delivered / Invalidated / InProgress
    created_at: str            # ISO 8601 from state file updated_at
    state_path: Optional[Path] = None  # full path to the state file


def _parse_frontmatter(text: str) -> dict:
    """Extract key: value pairs from YAML frontmatter block."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def get_sessions(cycle_id: str, stage: str, cache_dir: Path) -> List[SessionInfo]:
    """Scan the correct stage directory and return SessionInfo list."""
    stage_dir = cache_dir / cycle_id / _stage_subdir(stage)
    if not stage_dir.is_dir():
        return []
    sessions = []
    if stage in _STAGE_FLAT:
        ws = stage_dir / "session-state.md"
        if ws.exists():
            fm = _parse_frontmatter(ws.read_text(encoding="utf-8"))
            state = fm.get("current_state", "")
            if state in _FLAT_VALID_STATES:
                sessions.append(SessionInfo(
                    revision="r0",
                    state=state,
                    created_at=fm.get("updated_at", ""),
                    state_path=ws,
                ))
    else:
        for rev_dir in sorted(stage_dir.iterdir()):
            if not _STAGE_REVISION_PAT.match(rev_dir.name):
                continue
            ws = rev_dir / "workflow-state.md"
            if not ws.exists():
                continue
            fm = _parse_frontmatter(ws.read_text(encoding="utf-8"))
            state = fm.get("current_state", "")
            if state not in _VALID_STATES:
                continue  # silently skip old state names
            sessions.append(SessionInfo(
                revision=rev_dir.name,
                state=state,
                created_at=fm.get("updated_at", ""),
                state_path=ws,
            ))
    return sessions


def has_any_valid_session(cycle_id: str, stage: str, cache_dir: Path) -> bool:
    """Return True if at least one session has state != Invalidated."""
    return any(s.state != "Invalidated" for s in get_sessions(cycle_id, stage, cache_dir))


def current_effective_delivered(cycle_id: str, stage: str, cache_dir: Path) -> bool:
    """Return True if the latest non-Invalidated session has state == Delivered."""
    valid = [s for s in get_sessions(cycle_id, stage, cache_dir)
             if s.state != "Invalidated"]
    if not valid:
        return False
    latest = max(valid, key=lambda s: (s.created_at, s.revision))
    return latest.state == "Delivered"


def load_transitions(cycle_type: str) -> dict:
    """Load transition-table.json → {from_stage|None: set(to_stages)}."""
    tt = json.loads((_CONFIG_DIR / "transition-table.json").read_text(encoding="utf-8"))
    result: dict = {}
    for entry in tt.get(cycle_type, []):
        result.setdefault(entry.get("from"), set()).update(entry.get("to", []))
    return result


def load_stage_order(cycle_type: str) -> List[str]:
    """Derive ordered stage list from non-null transitions in transition-table.json."""
    transitions = load_transitions(cycle_type)
    forward = {k: next(iter(v)) for k, v in transitions.items() if k is not None and v}
    all_targets = set(forward.values())
    roots = [s for s in forward if s not in all_targets]
    order: List[str] = []
    current: Optional[str] = roots[0] if roots else None
    while current:
        order.append(current)
        current = forward.get(current)
    return order


def check_gate(cycle_id: str, to_stage: str, cycle_type: str,
               cache_dir: Path) -> Tuple[bool, str]:
    """Validate gate for to_stage using transition-table.json rules.

    Rule:
    1. Read cycle-state.json → current_stage (None = NULL / never started).
    2. Load allowed transitions from transition-table.json.
    3. Allowed next stages = transitions[current_stage]; re-entry always allowed.
    4. to_stage not in allowed set → BLOCK.
    5. Advancing (to_stage != current_stage): require current_stage Delivered.
    """
    transitions = load_transitions(cycle_type)
    all_stages = {s for v in transitions.values() for s in v} | \
                 {k for k in transitions if k is not None}
    if to_stage not in all_stages:
        return (True, "OK")

    current_stage = read_cycle_state(cycle_id, cache_dir)
    if current_stage is not None and current_stage not in all_stages:
        current_stage = None  # normalize stale / out-of-cycle values

    allowed = transitions.get(current_stage, set())
    is_reentry = (to_stage == current_stage)
    is_advance = (to_stage in allowed)

    if not is_reentry and not is_advance:
        expected = ", ".join(sorted(allowed)) or "terminal"
        return (
            False,
            f"Invalid transition: {current_stage or 'NULL'} → {to_stage}"
            f" (allowed: {expected})",
        )

    # Advancing requires current stage to be Delivered
    if is_advance and current_stage is not None:
        if not current_effective_delivered(cycle_id, current_stage, cache_dir):
            return (False, f"Gate blocked: {current_stage} is not Delivered")

    return (True, "OK")


def get_topic_doc(cycle_id: str, stage: str,
                  cache_dir: Path) -> Optional[Path]:
    """Return the latest Delivered doc path for the topic referenced by a feature, or None."""
    # Load cycle meta from cycles.json
    cj = cache_dir / "cycles.json"
    if not cj.exists():
        return None
    cycles_data = json.loads(cj.read_text(encoding="utf-8"))
    meta = cycles_data.get(cycle_id, {})
    if not isinstance(meta, dict):
        return None
    topic_id = meta.get("topic_id")
    if not topic_id:
        return None

    # Validate topic exists in cycles.json
    if topic_id not in cycles_data:
        raise ValueError(f"topic_id {topic_id!r} not found in cycles.json")

    # Resolve ref stage from transition-table.json
    tt = json.loads((_CONFIG_DIR / "transition-table.json").read_text(encoding="utf-8"))
    ref_stage = tt.get("topic_doc_stage", {}).get(stage)
    if ref_stage is None:
        return None

    # Find latest Delivered session in the topic container
    sessions = [s for s in get_sessions(topic_id, ref_stage, cache_dir)
                if s.state == "Delivered"]
    if not sessions:
        return None
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    doc_path = latest.state_path.parent if latest.state_path else None
    return doc_path if doc_path and doc_path.exists() else None
_PLATFORMS_DIR = Path(__file__).resolve().parent / "platforms"
_WRITE_TOOL_NAMES = frozenset({"Write", "Edit"})
_KNOWN_STAGES = frozenset({
    "diagnostic",
    "product-diagnostic", "tech-diagnostic",
    "product-plan", "tech-plan",
    "tech-work-order", "tech-code",
})


def _load_platform(platform: str):
    path = _PLATFORMS_DIR / f"{platform}.py"
    spec = importlib.util.spec_from_file_location(f"_platform_{platform}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_stage_module(stage: str):
    path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
    stage_scripts = str(path.parent)
    sys.path.insert(0, stage_scripts)
    sys.modules.pop("workflow_common", None)
    try:
        spec = importlib.util.spec_from_file_location(f"_{stage}_hook_guard", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        try:
            sys.path.remove(stage_scripts)
        except ValueError:
            pass
        sys.modules.pop("workflow_common", None)
        sys.modules.pop(f"_{stage}_hook_guard", None)


# Any .py under the lulu-dev-workflow skill root (any subdir).
_WORKFLOW_PY_PATH = re.compile(
    r"lulu-dev-workflow[/\\][^\s;|&\"']+\.py\b"
)

# Only stage entry start scripts call write_active_context(..., conversation_id=...).
# Shell paths: {stage}/scripts/start.py. tech-plan: compose-kernel/scripts/core/start.py.
# Orchestrator/control scripts (draft_control, session_control, etc.) must not
# receive injected --conversation-id — they use strict argparse.parse_args().
_CONV_ID_INJECT_SCRIPT_SUFFIXES = (
    "/scripts/start.py",
    "/compose-kernel/scripts/core/start.py",
)


def _should_inject_conversation_id(command: str) -> bool:
    if "--conversation-id" in command:
        return False
    if not re.search(r"\bpython3?\b", command):
        return False
    if not _WORKFLOW_PY_PATH.search(command):
        return False
    return any(suffix in command for suffix in _CONV_ID_INJECT_SCRIPT_SUFFIXES)


def _workflow_cache_dir(platform: str) -> Path:
    return Path.cwd() / f".cache/{platform}/lulu-dev-workflow"


def _read_active_entry(platform: str, conversation_id: str):
    if not conversation_id:
        return None
    return get_entry(Path.cwd(), platform, conversation_id)


def _read_active_stage(platform: str, conversation_id: str) -> Optional[str]:
    entry = _read_active_entry(platform, conversation_id)
    if entry is None:
        return None
    stage = entry.get("stage")
    return stage if stage in _KNOWN_STAGES else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform", default="cursor",
        choices=["cursor", "copilot", "claude"],
        help="Platform invoking this hook.",
    )
    args, _ = parser.parse_known_args()

    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"permission": "allow"}))
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return 0

    # Propagate platform to stage workflow_common.py via env var
    os.environ["LULU_PLATFORM"] = args.platform

    # Normalize payload to Cursor format
    platform_mod = _load_platform(args.platform)
    normalized = platform_mod.normalize(payload)

    # Early-return allow for non-write tools
    tool_name = str(normalized.get("tool_name") or "")

    # Inject conversation_id into lulu-dev-workflow shell commands
    if tool_name == "Shell":
        try:
            tool_input = normalized.get("tool_input") or {}
            command = tool_input.get("command", "")
            conv_id = (normalized.get("conversation_id") or "").strip()
            if conv_id and _should_inject_conversation_id(command):
                new_cmd = f"{command} --conversation-id {conv_id}"
                print(json.dumps({
                    "permission": "allow",
                    "updated_input": {"command": new_cmd},
                }))
                return 0
        except Exception:
            pass
        print(json.dumps({"permission": "allow"}))
        return 0

    if tool_name not in _WRITE_TOOL_NAMES:
        print(json.dumps({"permission": "allow"}))
        return 0

    # Determine active stage
    conv_id = (normalized.get("conversation_id") or "").strip()
    stage = _read_active_stage(args.platform, conv_id)
    if stage is None:
        print(json.dumps({"permission": "allow"}))
        return 0

    stage_path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
    if not stage_path.exists():
        print(json.dumps({"permission": "allow"}))
        return 0

    entry = _read_active_entry(args.platform, conv_id)
    if entry and current_effective_delivered(
        entry["cycle_id"], stage, _workflow_cache_dir(args.platform)
    ):
        print(json.dumps({"permission": "allow"}))
        return 0

    normalized_raw = json.dumps(normalized)
    sys.stdin = io.StringIO(normalized_raw)
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        mod = _load_stage_module(stage)
        mod.main()
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    if output:
        try:
            result = json.loads(output)
            print(json.dumps(result))
            return 0
        except json.JSONDecodeError:
            pass

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
