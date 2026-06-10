import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from archive_common import (  # noqa: E402
    TECH_CODE_CONFIG as CODE_CONFIG,
    archive_dir as _archive_dir,
    hot_root as _hot_root,
    is_conv_terminal,
    list_conv_ids,
)

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
_WORKFLOW_DIR_MAP = {
    "cursor":  Path(".cursor/lulu-dev-workflow"),
    "copilot": Path(".github/lulu-dev-workflow"),
}
WORKFLOW_DIR = _WORKFLOW_DIR_MAP.get(_PLATFORM, _WORKFLOW_DIR_MAP["cursor"])
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
STAGE = "tech-code"
CACHE_SUBDIR = "tech/code"
PLATFORM_CONFIG_PATH = WORKFLOW_DIR / "config.json"
SHARED_CONFIG_DEFAULT = Path("skill-config/lulu-dev-workflow/workflow-config.json")

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# archive-only: used by archive logic (Phase 4)
def code_hot_root() -> Path:
    return _hot_root(CODE_CONFIG)


def archive_code_dir(conversation_id: str) -> Path:
    return _archive_dir(CODE_CONFIG, conversation_id)


def session_base_dir(cycle_id: str) -> Path:
    return CACHE_DIR / cycle_id / CACHE_SUBDIR


def session_state_path(cycle_id: str) -> Path:
    return session_base_dir(cycle_id) / "session-state.md"


def doc_dir(cycle_id: str, session_round: int) -> Path:
    return session_base_dir(cycle_id) / f"s{session_round}"


def state_path(cycle_id: str, session_round: int) -> Path:
    return doc_dir(cycle_id, session_round) / "workflow-state.md"


def task_list_path(cycle_id: str, session_round: int) -> Path:
    return doc_dir(cycle_id, session_round) / "code-task-list.md"


def task_dir(cycle_id: str, session_round: int, task_id: str) -> Path:
    return doc_dir(cycle_id, session_round) / "tasks" / task_id


def approval_path(cycle_id: str, session_round: int) -> Path:
    return doc_dir(cycle_id, session_round) / "delivery-approval.md"


def list_code_conv_ids(code_root: Path) -> List[str]:
    """Return conv_id direct subdirectories of code/ (UUID or slug)."""
    return list_conv_ids(code_root)


def is_conv_completed(conv_dir: Path) -> Optional[bool]:
    """Return True if active session is Delivered, False if non-terminal, None if unreadable."""
    return is_conv_terminal(conv_dir, CODE_CONFIG)


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


def resolve_workflow_config_path(project_root: Path = Path(".")) -> Path:
    """Get shared workflow-config.json path via platform config pointer."""
    platform_cfg_path = project_root / PLATFORM_CONFIG_PATH
    if platform_cfg_path.exists():
        platform_cfg = read_json(platform_cfg_path, default={})
        wf_path = platform_cfg.get("workflowConfig")
        if wf_path:
            return project_root / wf_path
    return project_root / SHARED_CONFIG_DEFAULT


# ---------------------------------------------------------------------------
# Markdown state helpers
# ---------------------------------------------------------------------------

def write_session_state(path: Path, active_session: int) -> None:
    """Write session-state.md tracking the active TDD session round."""
    from session_state_schema import save_session_state

    save_session_state(path, active_session)


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


def read_md_field(path: Path, field: str, default: str = "") -> str:
    """Read a specific frontmatter field from a markdown file."""
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    fields = parse_frontmatter_fields(content)
    return fields.get(field, default)


def normalize_tool_path(raw_path: str, project_root: Path) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(project_root.resolve())
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def detect_cycle_type(cycle_id: str) -> str:
    """Return 'topic' if cycle_id starts with 'topic-', else 'feature'."""
    return "topic" if cycle_id.startswith("topic-") else "feature"


def load_container_meta(cache_dir: Path, cycle_id: str, cycle_type: str = None) -> dict:
    """Load cycle metadata from cycles.json.

    topic cycles: cycles.json must exist and contain cycle_id (strict).
    feature cycles: returns {} if cycles.json absent (backward compat).
    """
    _cycle_type = cycle_type or ("topic" if cycle_id.startswith("topic-") else "feature")
    json_file = cache_dir / "cycles.json"
    if not json_file.exists():
        if _cycle_type == "topic":
            raise ValueError(f"cycles.json not found: {json_file}")
        return {}
    data = json.loads(json_file.read_text(encoding="utf-8"))
    if cycle_id not in data:
        raise ValueError(f"cycle-id {cycle_id!r} not found in cycles.json")
    return data[cycle_id]


def write_active_context(
    project_root: Path,
    cycle_id: str,
    conversation_id: Optional[str] = None,
    stage: str = STAGE,
    cycle_type: str = "feature",
) -> None:
    import os
    import sys

    _scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    from active_context import resolve_conversation_id, write_entry  # noqa: E402

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        print(
            "警告：未提供 conversation_id，active-context 未更新，hook 不会保护本对话写入。",
            file=sys.stderr,
        )
        return
    platform = os.environ.get("LULU_PLATFORM", "cursor")
    write_entry(project_root, platform, conv_id, cycle_id, stage, cycle_type=cycle_type)


