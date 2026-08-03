import json
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir  # noqa: E402

from dec_domain_constraints_schema import KERNEL_STAGE  # noqa: E402
from dec_session_paths import session_cache_subdir  # noqa: E402

_PLATFORM = detect_platform()
CACHE_DIR = cache_dir(_PLATFORM)
STAGE = KERNEL_STAGE


def session_base_dir(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    root = project_root or Path.cwd()
    subdir = session_cache_subdir(
        root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
    )
    return CACHE_DIR / cycle_id / subdir


def session_state_path(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "session-state.md"


def gate_state_path(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "gate-state.json"


def registers_path(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "registers.json"


def decision_doc_path(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "decision-doc.md"


def gate_payloads_dir(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "gate-payloads"


def domain_constraints_path(
    cycle_id: str,
    stage: str = STAGE,
    *,
    project_root: Optional[Path] = None,
    constraints_path: Optional[Path] = None,
) -> Path:
    return session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    ) / "domain-constraints.json"


def write_session_state(path: Path, current_state: str) -> None:
    from dec_session_state_schema import write_session_state as _write

    _write(path, current_state)


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
