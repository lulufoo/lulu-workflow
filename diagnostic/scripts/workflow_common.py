from datetime import datetime, timezone
from pathlib import Path

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
STAGE = "diagnostic"


def diagnostic_hot_root() -> Path:
    return CACHE_DIR / "diagnostic"


def archive_diagnostic_dir(conversation_id: str) -> Path:
    return CACHE_DIR / "_archive" / conversation_id / "diagnostic"


def session_base_dir(feature_id: str) -> Path:
    return CACHE_DIR / feature_id / STAGE


def session_state_path(feature_id: str) -> Path:
    return session_base_dir(feature_id) / "session-state.md"


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
