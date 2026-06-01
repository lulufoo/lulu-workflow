import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
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


def session_base_dir(feature_id: str, stage: str = STAGE) -> Path:
    return CACHE_DIR / feature_id / _cache_subdir(stage)


def session_state_path(feature_id: str, stage: str = STAGE) -> Path:
    return session_base_dir(feature_id, stage) / "session-state.md"


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


def write_active_context(
    project_root: Path,
    feature_id: str,
    conversation_id: Optional[str] = None,
    stage: str = STAGE,
) -> None:
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
