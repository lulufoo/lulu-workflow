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

from active_context import get_entry

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _SKILL_ROOT / "config"

_VALID_STATES = frozenset({"Drafting", "Evaluating", "Delivered", "Invalidated"})


# ---------------------------------------------------------------------------
# Gate model: data classes and helpers
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    revision: str    # "r1", "r2", ...
    state: str       # Drafting / Evaluating / Delivered / Invalidated
    created_at: str  # ISO 8601 from workflow-state.md updated_at


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
    """Scan cache_dir/cycle_id/stage/r*/workflow-state.md and return SessionInfo list."""
    stage_dir = cache_dir / cycle_id / stage
    if not stage_dir.is_dir():
        return []
    sessions = []
    for rev_dir in sorted(stage_dir.iterdir()):
        if not re.match(r"^r\d+$", rev_dir.name):
            continue
        ws = rev_dir / "workflow-state.md"
        if not ws.exists():
            continue
        fm = _parse_frontmatter(ws.read_text(encoding="utf-8"))
        state = fm.get("current_state", "")
        if state not in _VALID_STATES:
            continue  # silently skip old state names
        created_at = fm.get("updated_at", "")
        sessions.append(SessionInfo(revision=rev_dir.name, state=state, created_at=created_at))
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


def load_stage_order(cycle_type: str, config_dir: Path) -> List[str]:
    """Read stage order from config/state-machine.json."""
    sm = json.loads((config_dir / "state-machine.json").read_text(encoding="utf-8"))
    return sm["cycle_types"][cycle_type]["stages"]


def check_gate(cycle_id: str, to_stage: str, cycle_type: str,
               cache_dir: Path, config_dir: Path) -> Tuple[bool, str]:
    """Validate gate for to_stage using the sequential_all_prior rule.

    Rule: for any to_stage, all stages that appear before it in the stage order
    AND have at least one valid (non-Invalidated) session must have
    current_effective_delivered == True.
    Stages with no valid sessions are exempt (allows skipping optional stages,
    e.g. null → tech-diagnostic bypassing the product phase).
    """
    stages = load_stage_order(cycle_type, config_dir)
    if to_stage not in stages:
        return (True, "OK")
    idx = stages.index(to_stage)
    prior = stages[:idx]
    for stage in prior:
        if has_any_valid_session(cycle_id, stage, cache_dir):
            if not current_effective_delivered(cycle_id, stage, cache_dir):
                return (False, f"Gate blocked: {stage} is not Delivered")
    return (True, "OK")


def get_topic_doc(cycle_id: str, stage: str,
                  cache_dir: Path, config_dir: Path) -> Optional[Path]:
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

    # Resolve ref stage
    sm = json.loads((config_dir / "state-machine.json").read_text(encoding="utf-8"))
    ref_stage = sm.get("topic_doc_stage", {}).get(stage)
    if ref_stage is None:
        return None

    # Find latest Delivered session in the topic container
    sessions = [s for s in get_sessions(topic_id, ref_stage, cache_dir)
                if s.state == "Delivered"]
    if not sessions:
        return None
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    doc_path = cache_dir / topic_id / ref_stage / latest.revision
    return doc_path if doc_path.exists() else None
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


def _should_inject_conversation_id(command: str) -> bool:
    if "--conversation-id" in command:
        return False
    if not re.search(r"\bpython3?\b", command):
        return False
    return bool(_WORKFLOW_PY_PATH.search(command))


def _read_active_stage(platform: str, conversation_id: str) -> Optional[str]:
    if not conversation_id:
        return None
    entry = get_entry(Path.cwd(), platform, conversation_id)
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
