import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SKILL_ROOT = Path(__file__).resolve().parents[1]
WHITELIST_PATH = SKILL_ROOT / "transition-whitelist.json"

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
_SCRIPTS_DIR = Path(__file__).resolve().parent

WORKFLOW_DIR = _WORKFLOW_DIR_MAP.get(_PLATFORM, _WORKFLOW_DIR_MAP["cursor"])
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
STAGE = "product-plan"
CACHE_SUBDIR = "product/plan"
PLATFORM_CONFIG_PATH = WORKFLOW_DIR / "config.json"
SHARED_CONFIG_DEFAULT = Path("skill-config/lulu-dev-workflow/workflow-config.json")
HOOKS_JSON_PATH = _HOOKS_JSON_MAP.get(_PLATFORM, _HOOKS_JSON_MAP["cursor"])
HOOK_COMMAND = f"python3 {_SCRIPTS_DIR / 'hook_guard.py'}"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def session_base_dir(feature_id: str) -> Path:
    return CACHE_DIR / feature_id / CACHE_SUBDIR


def session_state_path(feature_id: str) -> Path:
    return session_base_dir(feature_id) / "session-state.md"


def doc_dir(feature_id: str, doc_round: int) -> Path:
    return session_base_dir(feature_id) / f"revision{doc_round}"


def state_path(feature_id: str, doc_round: int) -> Path:
    return doc_dir(feature_id, doc_round) / "workflow-state.md"


def approval_path(feature_id: str, doc_round: int) -> Path:
    return doc_dir(feature_id, doc_round) / "human-delivery-gate.md"


def eval_round_dir(feature_id: str, doc_round: int, evaluate_round: int) -> Path:
    return doc_dir(feature_id, doc_round) / f"evaluate{evaluate_round}"


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

def write_md_state(path: Path, current_state: str, evaluate_round: int = 0) -> None:
    """Write revision{N}/workflow-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"workflow: product-plan\n"
        f"current_state: {current_state}\n"
        f"evaluate_round: {evaluate_round}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def write_session_state(path: Path, active_doc: int) -> None:
    """Write session-state.md tracking the active product document round."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"active_doc: {active_doc}\n"
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
    """Extract current_state from YAML frontmatter in a markdown file."""
    fields = parse_frontmatter_fields(content)
    return fields.get("current_state") or None


def read_md_field(path: Path, field: str, default: str = "") -> str:
    """Read a specific frontmatter field from a markdown file."""
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    fields = parse_frontmatter_fields(content)
    return fields.get(field, default)


def read_md_state(path: Path, default: str = "Drafting") -> str:
    """Read current_state from workflow-state.md, returning default if absent."""
    state = read_md_field(path, "current_state", default=default)
    return state if state else default


def is_current_session_active(project_root: Path, feature_id: str) -> bool:
    """Return True if this conversation has any non-Delivered planning session."""
    if not feature_id:
        return False
    base = project_root / session_base_dir(feature_id)
    if not base.exists():
        return False
    for state_file in base.glob("revision*/workflow-state.md"):
        if read_md_state(state_file, default="Drafting") != "Delivered":
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


def write_active_context(
    project_root: Path,
    feature_id: str,
    conversation_id: Optional[str] = None,
    stage: str = STAGE,
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
    write_entry(project_root, platform, conv_id, feature_id, stage)
