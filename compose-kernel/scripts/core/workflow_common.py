import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_CORE = Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
from workflow_paths import (  # noqa: E402
    COMPOSE_SESSION_TRANSITION,
    WORKFLOW_ROOT,
    WORKFLOW_SCRIPTS,
    load_profile,
    shell_path,
)

_PROFILE = load_profile("tech-plan")
SKILL_ROOT = WORKFLOW_ROOT / _PROFILE["shell_dir"]
WHITELIST_PATH = COMPOSE_SESSION_TRANSITION

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
_WORKFLOW_DIR_MAP = {
    "cursor":  Path(".cursor/lulu-dev-workflow"),
    "copilot": Path(".github/lulu-dev-workflow"),
}
_HOOKS_JSON_MAP = {
    "cursor":  Path(".cursor/hooks.json"),
    "copilot": Path(".github/hooks/hooks.json"),
}

WORKFLOW_DIR = _WORKFLOW_DIR_MAP.get(_PLATFORM, _WORKFLOW_DIR_MAP["cursor"])
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
STAGE = _PROFILE["stage_name"]
CACHE_SUBDIR = _PROFILE["cache_subdir"]
PLATFORM_CONFIG_PATH = WORKFLOW_DIR / "config.json"
SHARED_CONFIG_DEFAULT = Path("skill-config/lulu-dev-workflow/workflow-config.json")
HOOKS_JSON_PATH = _HOOKS_JSON_MAP.get(_PLATFORM, _HOOKS_JSON_MAP["cursor"])

# Absolute path for hook command (workspace-local install; shell hook_guard)
HOOK_COMMAND = f"python3 {shell_path(_PROFILE, 'hook_guard')}"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def session_base_dir(cycle_id: str) -> Path:
    return CACHE_DIR / cycle_id / CACHE_SUBDIR


def session_state_path(cycle_id: str) -> Path:
    return session_base_dir(cycle_id) / "session-state.md"


def doc_dir(cycle_id: str, doc_round: int) -> Path:
    return session_base_dir(cycle_id) / f"revision{doc_round}"


def state_path(cycle_id: str, doc_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / "workflow-state.md"


def approval_path(cycle_id: str, doc_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / "human-delivery-gate.md"


def tech_doc_path(cycle_id: str, doc_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / "tech-doc.md"


def decision_doc_path(cycle_id: str) -> Path:
    return CACHE_DIR / cycle_id / "tech" / "diagnostic" / "decision-doc.md"


def eval_round_dir(cycle_id: str, doc_round: int, evaluate_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / f"evaluate{evaluate_round}"


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

def read_json(path: Path, default=None) -> Dict[str, Any]:
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


def is_current_session_active(project_root: Path, cycle_id: str) -> bool:
    """Return True if this conversation has any non-Delivered planning session."""
    from workflow_state_schema import read_current_state  # noqa: WPS433

    if not cycle_id:
        return False
    base = project_root / session_base_dir(cycle_id)
    if not base.exists():
        return False
    for state_file in base.glob("revision*/workflow-state.md"):
        if read_current_state(state_file, default="Drafting") != "Delivered":
            return True
    return False


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

    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    from active_context_schema import resolve_conversation_id, write_entry  # noqa: E402

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        print(
            "警告：未提供 conversation_id，active-context 未更新，hook 不会保护本对话写入。",
            file=sys.stderr,
        )
        return
    platform = os.environ.get("LULU_PLATFORM", "cursor")
    write_entry(project_root, platform, conv_id, cycle_id, stage, cycle_type=cycle_type)
