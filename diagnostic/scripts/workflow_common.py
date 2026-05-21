from datetime import datetime, timezone
from pathlib import Path

WORKFLOW_DIR = Path(".cursor/lulu-dev-workflow")
CACHE_DIR = Path(".cache/lulu-dev-workflow")


def diagnostic_hot_root() -> Path:
    return CACHE_DIR / "diagnostic"


def archive_diagnostic_dir(conversation_id: str) -> Path:
    return CACHE_DIR / "_archive" / conversation_id / "diagnostic"


def session_base_dir(conversation_id: str) -> Path:
    return diagnostic_hot_root() / conversation_id


def session_state_path(conversation_id: str) -> Path:
    return session_base_dir(conversation_id) / "session-state.md"


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
