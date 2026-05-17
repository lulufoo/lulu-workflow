import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SKILL_ROOT = Path.home() / ".cursor/skills/lulu-dev-workflow/product"
WHITELIST_PATH = SKILL_ROOT / "transition-whitelist.json"

WORKFLOW_DIR = Path(".cursor/lulu-dev-workflow")
CACHE_DIR = Path(".cache/lulu-dev-workflow")
CONFIG_PATH = WORKFLOW_DIR / "workflow-config.json"
HOOKS_JSON_PATH = Path(".cursor/hooks.json")
HOOK_COMMAND = "python3 ~/.cursor/skills/lulu-dev-workflow/product/scripts/hook_guard.py"


def session_dir(conversation_id: str) -> Path:
    return CACHE_DIR / "product" / conversation_id


def state_path(conversation_id: str) -> Path:
    return session_dir(conversation_id) / "workflow-state.md"


def approval_path(conversation_id: str) -> Path:
    return session_dir(conversation_id) / "human-delivery-gate.md"


def hook_entry() -> Dict[str, Any]:
    return {
        "matcher": "Write|Edit",
        "command": HOOK_COMMAND,
        "timeout": 5,
        "failClosed": True,
    }


def read_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path.exists():
        if default is None:
            raise FileNotFoundError(path)
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def write_md_state(path: Path, current_state: str) -> None:
    """Write workflow-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = f"---\nversion: 1\nworkflow: product\ncurrent_state: {current_state}\nupdated_at: {now}\n---\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def parse_frontmatter_state(content: str) -> Optional[str]:
    """Extract current_state from YAML frontmatter in a markdown file."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return None
    fm_content = fm_match.group(1)
    state_match = re.search(r"^current_state:\s*(\w+)", fm_content, re.MULTILINE)
    if state_match:
        return state_match.group(1).strip()
    return None


def read_md_state(path: Path, default: str = "Drafting") -> str:
    """Read current_state from workflow-state.md, returning default if absent."""
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    state = parse_frontmatter_state(content)
    return state if state else default


def normalize_tool_path(raw_path: str, project_root: Path) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(project_root.resolve())
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def merge_hook_entry(hooks_payload: Dict[str, Any]) -> Dict[str, Any]:
    hooks_payload.setdefault("version", 1)
    hooks = hooks_payload.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("preToolUse", [])
    entry = hook_entry()
    new_cmd = entry["command"]
    old_cmds = {
        "python3 ~/.cursor/skills/product-doc-workflow/scripts/hook_guard.py",
        "python3 .cursor/hooks/product-doc-transition-guard.py",
    }

    for index, existing in enumerate(pre_tool_use):
        cmd = existing.get("command", "")
        if cmd == new_cmd or cmd in old_cmds:
            pre_tool_use[index] = entry
            return hooks_payload

    pre_tool_use.append(entry)
    return hooks_payload
