import json
from datetime import datetime, timezone
from pathlib import Path

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")
STAGE = "diagnostic"

_STAGE_TO_SUBDIR: dict[str, str] = {
    "product-diagnostic": "product-plan/diagnostic",
    "tech-diagnostic": "tech-plan/diagnostic",
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


def write_active_context(project_root: Path, feature_id: str, stage: str = STAGE) -> None:
    path = project_root / CACHE_DIR / "active-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"feature_id": feature_id, "stage": stage}, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
