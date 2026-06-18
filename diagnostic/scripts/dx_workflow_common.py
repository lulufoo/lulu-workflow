import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir  # noqa: E402

_PLATFORM = detect_platform()
CACHE_DIR = cache_dir(_PLATFORM)
STAGE = "diagnostic"

_STAGE_TO_SUBDIR: dict[str, str] = {
    "product-diagnostic": "product/diagnostic",
    "tech-diagnostic": "tech/diagnostic",
    "diagnostic": "diagnostic",
}


def _cache_subdir(stage: str) -> str:
    return _STAGE_TO_SUBDIR.get(stage, stage)


def diagnostic_hot_root() -> Path:
    return CACHE_DIR / "diagnostic"


def archive_diagnostic_dir(conversation_id: str) -> Path:
    return CACHE_DIR / "_archive" / conversation_id / "diagnostic"


def session_base_dir(cycle_id: str, stage: str = STAGE) -> Path:
    return CACHE_DIR / cycle_id / _cache_subdir(stage)


def session_state_path(cycle_id: str, stage: str = STAGE) -> Path:
    return session_base_dir(cycle_id, stage) / "session-state.md"


def write_session_state(path: Path, current_state: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"current_state: {current_state}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    path.write_text(content, encoding="utf-8")


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
    _scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    from active_context_schema import resolve_conversation_id, write_entry  # noqa: E402

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        print(
            "警告：未提供 conversation_id，active-context 未更新，hook 不会保护本对话写入。",
            file=sys.stderr,
        )
        return
    platform = detect_platform()
    write_entry(project_root, platform, conv_id, cycle_id, stage, cycle_type=cycle_type)
