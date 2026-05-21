import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from archive_common import (  # noqa: E402
    CODE_CONFIG,
    archive_dir as _archive_dir,
    hot_root as _hot_root,
    is_conv_terminal,
    list_conv_ids,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]  # .../tdd
WHITELIST_PATH = SKILL_ROOT / "transition-whitelist.json"

WORKFLOW_DIR = Path(".cursor/lulu-dev-workflow")
CACHE_DIR = Path(".cache/lulu-dev-workflow")
CONFIG_PATH = WORKFLOW_DIR / "workflow-config.json"
HOOKS_JSON_PATH = Path(".cursor/hooks.json")

_SCRIPTS_DIR = Path(__file__).resolve().parent
HOOK_COMMAND = f"python3 {_SCRIPTS_DIR / 'hook_guard.py'}"

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def code_hot_root() -> Path:
    return _hot_root(CODE_CONFIG)


def archive_code_dir(conversation_id: str) -> Path:
    return _archive_dir(CODE_CONFIG, conversation_id)


def session_base_dir(conversation_id: str) -> Path:
    return code_hot_root() / conversation_id


def session_state_path(conversation_id: str) -> Path:
    return session_base_dir(conversation_id) / "session-state.md"


def doc_dir(conversation_id: str, session_round: int) -> Path:
    return session_base_dir(conversation_id) / f"s{session_round}"


def state_path(conversation_id: str, session_round: int) -> Path:
    return doc_dir(conversation_id, session_round) / "workflow-state.md"


def task_list_path(conversation_id: str, session_round: int) -> Path:
    return doc_dir(conversation_id, session_round) / "code-task-list.md"


def task_dir(conversation_id: str, session_round: int, task_id: str) -> Path:
    return doc_dir(conversation_id, session_round) / "tasks" / task_id


def approval_path(conversation_id: str, session_round: int) -> Path:
    return doc_dir(conversation_id, session_round) / "human-delivery-gate.md"


def list_code_conv_ids(code_root: Path) -> List[str]:
    """Return conv_id direct subdirectories of code/ (UUID or slug)."""
    return list_conv_ids(code_root)


def is_conv_completed(conv_dir: Path) -> Optional[bool]:
    """Return True if active session is Completed, False if non-terminal, None if unreadable."""
    return is_conv_terminal(conv_dir, CODE_CONFIG)


def hook_entry() -> Dict[str, Any]:
    return {
        "matcher": "Write|Edit",
        "command": HOOK_COMMAND,
        "timeout": 5,
        "failClosed": True,
    }


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is None:
            raise FileNotFoundError(path)
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


# ---------------------------------------------------------------------------
# Markdown state helpers
# ---------------------------------------------------------------------------

def write_md_state(
    path: Path,
    current_state: str,
    mode: str = "",
    task_list_ref: str = "",
    current_task: str = "",
    current_phase: str = "",
) -> None:
    """Write s{N}/workflow-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"workflow: tdd\n"
        f"current_state: {current_state}\n"
        f"mode: {mode}\n"
        f"task_list_ref: {task_list_ref}\n"
        f"current_task: {current_task}\n"
        f"current_phase: {current_phase}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def write_session_state(path: Path, active_session: int) -> None:
    """Write session-state.md tracking the active TDD session round."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"active_session: {active_session}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def parse_frontmatter_fields(content: str) -> Dict[str, str]:
    """Extract all key: value pairs from YAML frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return {}
    result: Dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        kv_match = re.match(r"^(\w+):\s*(.*)", line)
        if kv_match:
            result[kv_match.group(1)] = kv_match.group(2).strip()
    return result


def parse_frontmatter_state(content: str) -> Optional[str]:
    """Extract current_state from YAML frontmatter."""
    fields = parse_frontmatter_fields(content)
    return fields.get("current_state") or None


def read_md_field(path: Path, field: str, default: str = "") -> str:
    """Read a specific frontmatter field from a markdown file."""
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    fields = parse_frontmatter_fields(content)
    return fields.get(field, default)


def read_md_state(path: Path, default: str = "Executing") -> str:
    """Read current_state from workflow-state.md, returning default if absent."""
    state = read_md_field(path, "current_state", default=default)
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

    for index, existing in enumerate(pre_tool_use):
        if existing.get("command") == new_cmd:
            pre_tool_use[index] = entry
            return hooks_payload

    pre_tool_use.append(entry)
    return hooks_payload


# ---------------------------------------------------------------------------
# code-task-list.md helpers
# ---------------------------------------------------------------------------

def parse_task_list_md(content: str) -> List[Dict[str, Any]]:
    """
    Parse code-task-list.md checkbox lines.
    Line format:
      - [x] t1 · Title · `target_file` · ✅ Done (depends: t2, t3)
      - [ ] t2 · Title · `target_file` · ⏳ Pending
    Returns list of dicts: {id, done, title, target_file, phase, depends}
    """
    tasks = []
    for line in content.splitlines():
        m = re.match(
            r"^\s*-\s*\[([ xX])\]\s+(\w+)\s+·\s+(.+?)\s+·\s+`(.+?)`\s+·\s+(.+?)(?:\s+\(depends:\s*([^)]+)\))?$",
            line,
        )
        if not m:
            continue
        checked, task_id, title, target_file, status, deps_raw = m.groups()
        depends = [d.strip() for d in deps_raw.split(",")] if deps_raw else []
        tasks.append(
            {
                "id": task_id,
                "done": checked.lower() == "x",
                "title": title.strip(),
                "target_file": target_file.strip(),
                "phase": status.strip(),
                "depends": depends,
            }
        )
    return tasks


def all_tasks_done(tl_path: Path) -> bool:
    """Return True if all tasks in code-task-list.md are checked [x]."""
    if not tl_path.exists():
        return False
    tasks = parse_task_list_md(tl_path.read_text(encoding="utf-8"))
    return bool(tasks) and all(t["done"] for t in tasks)


def get_task_depends(tl_path: Path, task_id: str) -> List[str]:
    """Return the depends list for a given task_id."""
    if not tl_path.exists():
        return []
    tasks = parse_task_list_md(tl_path.read_text(encoding="utf-8"))
    for t in tasks:
        if t["id"] == task_id:
            return t["depends"]
    return []


def get_done_task_ids(tl_path: Path) -> List[str]:
    """Return list of task IDs that are checked [x]."""
    if not tl_path.exists():
        return []
    tasks = parse_task_list_md(tl_path.read_text(encoding="utf-8"))
    return [t["id"] for t in tasks if t["done"]]
