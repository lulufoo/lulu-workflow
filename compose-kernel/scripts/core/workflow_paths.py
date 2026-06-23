"""Path constants and profile loading for compose-kernel scripts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
EVAL_SCRIPTS = WORKFLOW_ROOT / "eval" / "scripts"
WORKFLOW_SCRIPTS = WORKFLOW_ROOT / "scripts"
COMPOSE_KERNEL_ROOT = WORKFLOW_ROOT / "compose-kernel"
KERNEL_TRANSITIONS = COMPOSE_KERNEL_ROOT / "transitions"
KERNEL_SCHEMES = COMPOSE_KERNEL_ROOT / "schemes"
COMPOSE_SESSION_TRANSITION = KERNEL_TRANSITIONS / "compose-session.json"
KERNEL_TEMPLATES = COMPOSE_KERNEL_ROOT / "templates"
DEFAULT_COMPOSE_PROFILE_ID = "tech-plan"
CORE_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "core"
SECTION_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "section"
SCOPE_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "scope"
IO_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "io"
SCHEMA_SECTION_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "schema" / "section"
SCHEMA_SECTION_REGISTRY_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "registry"
SCHEMA_SECTION_ROUND_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "round"
SCHEMA_SECTION_DOCUMENT_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "document"
SCHEMA_SECTION_SCOPE_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "scope"
SCHEMA_SESSION_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "schema" / "session"
SCHEMA_SCRIPTS = COMPOSE_KERNEL_ROOT / "scripts" / "schema"

PROFILE_POINTER_NAME = ".compose-profile-path"
COMPOSE_PROFILE_FILENAME = "compose-profile.json"
ACTIVE_COMPOSE_STAGE_IDS = ("tech-plan", "tech-design", "product-spec")

# Legacy: tech-arch placeholder only
PROFILES_DIR = COMPOSE_KERNEL_ROOT / "profiles"

_profile_cache: dict[str, dict[str, Any]] = {}


def compose_profile_path(profile_id: str) -> Path:
    """Authoring SSOT: WORKFLOW_ROOT/{profile_id}/compose-profile.json."""
    pid = profile_id.strip()
    return WORKFLOW_ROOT / pid / COMPOSE_PROFILE_FILENAME


def _cache_key(path: Path) -> str:
    return str(path.resolve())


def load_profile_json(path: Path) -> dict[str, Any]:
    """Load and cache profile JSON from an explicit file path."""
    key = _cache_key(path)
    if key in _profile_cache:
        return _profile_cache[key]
    if not path.is_file():
        raise FileNotFoundError(f"compose profile not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _profile_cache[key] = data
    return data


def _relative_to_project_root(project_root: Path, target: Path) -> str:
    root = project_root.resolve()
    resolved = target.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_from_project_root(project_root: Path, raw: str) -> Path:
    path = Path(raw.strip())
    if path.is_absolute():
        return path.resolve()
    return (project_root.resolve() / path).resolve()


def session_pointer_path(
    project_root: Path,
    cycle_id: str,
    cache_subdir: str,
) -> Path:
    from workflow_common import CACHE_DIR  # noqa: WPS433

    return (
        project_root.resolve()
        / CACHE_DIR
        / cycle_id.strip()
        / cache_subdir.strip()
        / PROFILE_POINTER_NAME
    )


def write_profile_pointer(
    project_root: Path,
    cycle_id: str,
    cache_subdir: str,
    profile_json_path: Path,
) -> Path:
    """Write session pointer with path relative to project_root."""
    pointer = session_pointer_path(project_root, cycle_id, cache_subdir)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    rel = _relative_to_project_root(project_root, profile_json_path)
    pointer.write_text(rel + "\n", encoding="utf-8")
    return pointer


def read_profile_pointer(session_base: Path, project_root: Path) -> Path:
    pointer = session_base / PROFILE_POINTER_NAME
    if not pointer.is_file():
        raise FileNotFoundError(
            f"compose profile pointer not found: {pointer}. "
            f"Run stage start with --profile-path first.",
        )
    raw = pointer.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"empty compose profile pointer: {pointer}")
    resolved = _resolve_from_project_root(project_root, raw)
    if not resolved.is_file():
        raise FileNotFoundError(
            f"compose profile pointer targets missing file: {resolved} (from {pointer})",
        )
    return resolved


def resolve_compose_session_base(
    project_root: Path,
    cycle_id: str,
    profile_id: str,
) -> Path:
    """Locate session base via .compose-profile-path under cycle cache."""
    from workflow_common import CACHE_DIR  # noqa: WPS433

    pid = profile_id.strip()
    cid = cycle_id.strip()
    cycle_dir = project_root.resolve() / CACHE_DIR / cid
    if not cycle_dir.is_dir():
        raise FileNotFoundError(
            f"cycle cache not found: {cycle_dir}. "
            f"Run stage start with --profile-path first.",
        )
    for pointer in sorted(cycle_dir.rglob(PROFILE_POINTER_NAME)):
        try:
            profile_path = read_profile_pointer(pointer.parent, project_root)
            data = load_profile_json(profile_path)
        except (OSError, json.JSONDecodeError, ValueError, FileNotFoundError):
            continue
        if str(data.get("profile_id", "")).strip() == pid:
            return pointer.parent
    raise FileNotFoundError(
        f"no compose profile pointer for {pid!r} under cycle {cid!r} ({cycle_dir})",
    )


def resolve_cycle_id(
    project_root: Path,
    *,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Resolve cycle id: explicit arg, env, then active-context."""
    if cycle_id and cycle_id.strip():
        return cycle_id.strip()
    env_val = os.environ.get("LULU_CYCLE_ID", "").strip()
    if env_val:
        return env_val
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    from active_context_schema import get_entry, resolve_conversation_id  # noqa: WPS433
    from workflow_common import detect_platform  # noqa: WPS433

    conv_id = resolve_conversation_id(conversation_id)
    if conv_id:
        entry = get_entry(project_root.resolve(), detect_platform(), conv_id)
        if entry and entry.get("cycle_id"):
            return str(entry["cycle_id"]).strip()
    raise ValueError(
        "cycle_id required: pass --cycle-id, set LULU_CYCLE_ID, "
        "or ensure active-context has an entry for this conversation",
    )


def load_profile(
    profile_id: str | None = None,
    *,
    project_root: Path | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Load compose profile JSON (session pointer or authoring path).

    When ``project_root`` is set and a cycle id is explicit or resolvable from
    env/active-context, the session ``.compose-profile-path`` is required (no
    fallback to authoring). Authoring path is used only when ``project_root`` is
    omitted, or when no cycle id can be resolved.
    """
    pid = (profile_id or DEFAULT_COMPOSE_PROFILE_ID).strip()
    if project_root is None:
        return load_profile_json(compose_profile_path(pid))

    root = project_root.resolve()
    explicit_cycle = (cycle_id or "").strip()
    if explicit_cycle:
        session_base = resolve_compose_session_base(root, explicit_cycle, pid)
        profile_path = read_profile_pointer(session_base, root)
        return load_profile_json(profile_path)

    try:
        resolved_cycle = resolve_cycle_id(
            root,
            cycle_id=None,
            conversation_id=conversation_id,
        )
    except ValueError:
        return load_profile_json(compose_profile_path(pid))

    session_base = resolve_compose_session_base(root, resolved_cycle, pid)
    profile_path = read_profile_pointer(session_base, root)
    return load_profile_json(profile_path)


def read_profile_for_start(profile_json_path: Path, profile_id: str) -> dict[str, Any]:
    """Read profile JSON at start before session pointer exists."""
    data = load_profile_json(profile_json_path.resolve())
    pid = profile_id.strip()
    if str(data.get("profile_id", "")).strip() != pid:
        raise ValueError(
            f"profile_id mismatch: --profile {pid!r} vs JSON {data.get('profile_id')!r}",
        )
    stage = str(data.get("stage_name", pid)).strip()
    if stage != pid:
        raise ValueError(f"stage_name {stage!r} != profile {pid!r}")
    return data


def validate_compose_profile_path(profile_id: str, profile_json_path: Path) -> None:
    """Ensure --profile-path matches authoring location (decision 1A)."""
    expected = compose_profile_path(profile_id).resolve()
    actual = profile_json_path.resolve()
    if actual != expected:
        raise ValueError(
            f"--profile-path must be {expected.as_posix()}; got {actual.as_posix()}",
        )


def shell_path(profile: dict[str, Any], key: str) -> Path:
    """Resolve a shell_paths entry relative to WORKFLOW_ROOT."""
    shell_paths = profile.get("shell_paths") or {}
    rel = shell_paths.get(key)
    if not rel:
        raise KeyError(f"shell_paths.{key} missing in profile {profile.get('profile_id')!r}")
    return WORKFLOW_ROOT / rel


def seed_profile_pointer_for_tests(
    project_root: Path,
    cycle_id: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Test helper: write pointer from authoring compose-profile.json."""
    data = load_profile_json(compose_profile_path(profile_id))
    cache_subdir = str(data.get("cache_subdir", "")).strip()
    if not cache_subdir:
        raise ValueError(f"cache_subdir missing in profile {profile_id!r}")
    return write_profile_pointer(
        project_root,
        cycle_id,
        cache_subdir,
        compose_profile_path(profile_id),
    )
