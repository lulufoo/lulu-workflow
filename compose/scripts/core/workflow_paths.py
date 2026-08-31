"""Path constants and profile loading for compose scripts."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
EVAL_SCRIPTS = WORKFLOW_ROOT / "eval" / "scripts"
WORKFLOW_SCRIPTS = WORKFLOW_ROOT / "scripts"
COMPOSE_ROOT = WORKFLOW_ROOT / "compose"
KERNEL_TRANSITIONS = COMPOSE_ROOT / "transitions"
KERNEL_SCHEMES = COMPOSE_ROOT / "schemes"
COMPOSE_SESSION_TRANSITION = KERNEL_TRANSITIONS / "compose-session.json"
KERNEL_TEMPLATES = COMPOSE_ROOT / "templates"
DEFAULT_COMPOSE_PROFILE_ID = "lulu-plan"
CORE_SCRIPTS = COMPOSE_ROOT / "scripts" / "core"
SECTION_SCRIPTS = COMPOSE_ROOT / "scripts" / "section"
SCOPE_SCRIPTS = COMPOSE_ROOT / "scripts" / "scope"
IO_SCRIPTS = COMPOSE_ROOT / "scripts" / "io"
SCHEMA_SECTION_SCRIPTS = COMPOSE_ROOT / "scripts" / "schema" / "section"
SCHEMA_SECTION_REGISTRY_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "registry"
SCHEMA_SECTION_DOCUMENT_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "document"
SCHEMA_SECTION_SCOPE_SCRIPTS = SCHEMA_SECTION_SCRIPTS / "scope"
SCHEMA_SESSION_SCRIPTS = COMPOSE_ROOT / "scripts" / "schema" / "session"
SCHEMA_SCRIPTS = COMPOSE_ROOT / "scripts" / "schema"

ACTIVE_PROFILE_NAME = ".compose-active-profile"
COMPOSE_PROFILE_FILENAME = "compose-profile.json"

_profile_cache: dict[str, dict[str, Any]] = {}
_REVISION_DIR_PATTERN = re.compile(r"revision[1-9]\d*")
_SLICE_DIR_PATTERN = re.compile(r"L[1-9]\d*")


@dataclass(frozen=True)
class RevisionRuntimeProfile:
    """Runtime profile and normalized paths owned by a revision."""

    profile_path: Path
    profile_data: dict[str, Any]
    profile_id: str
    revision_root: Path
    session_base: Path


def active_compose_stage_ids(*, workflow_root: Path | None = None) -> tuple[str, ...]:
    """Discover active compose stages by scanning for compose-profile.json.

    A stage counts as active when ``{workflow_root}/{dir_name}/compose-profile.json``
    exists, parses as JSON, ``profile_id`` matches ``dir_name``, and ``status`` is
    not ``placeholder_phase2``.
    """
    root = (workflow_root or WORKFLOW_ROOT).resolve()
    ids: list[str] = []
    for candidate in sorted(root.iterdir(), key=lambda path: path.name):
        if not candidate.is_dir():
            continue
        profile_path = candidate / COMPOSE_PROFILE_FILENAME
        if not profile_path.is_file():
            continue
        try:
            data = load_profile_json(profile_path)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") == "placeholder_phase2":
            continue
        if str(data.get("profile_id", "")).strip() != candidate.name:
            continue
        ids.append(candidate.name)
    return tuple(ids)


def compose_profile_path(profile_id: str) -> Path:
    """Authoring SSOT: WORKFLOW_ROOT/{profile_id}/compose-profile.json."""
    pid = profile_id.strip()
    return WORKFLOW_ROOT / pid / COMPOSE_PROFILE_FILENAME


def _cache_key(path: Path) -> str:
    return str(path.resolve())


def load_profile_json(path: Path) -> dict[str, Any]:
    """Load and cache profile JSON from an explicit file path.

    Returns a deep copy so callers can overlay fields without poisoning the cache.
    """
    key = _cache_key(path)
    if key not in _profile_cache:
        if not path.is_file():
            raise FileNotFoundError(f"compose profile not found: {path}")
        _profile_cache[key] = json.loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(_profile_cache[key])


def cache_subdir_for_profile(profile_id: str) -> str:
    data = load_profile_json(compose_profile_path(profile_id))
    subdir = str(data.get("cache_subdir", "")).strip()
    if not subdir:
        raise ValueError(f"cache_subdir missing in profile {profile_id!r}")
    return subdir


def compose_session_base(
    project_root: Path,
    cycle_id: str,
    profile_id: str,
) -> Path:
    """Deterministic session directory: cache / cycle / cache_subdir."""
    from workflow_common import CACHE_DIR  # noqa: WPS433

    return (
        project_root.resolve()
        / CACHE_DIR
        / cycle_id.strip()
        / cache_subdir_for_profile(profile_id)
    )


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
        / "session-state.md"
    )


def _write_session_runtime_binding(
    session_base: Path,
    profile_json_path: Path,
    *,
    active_doc: int = 1,
) -> Path:
    from session_state_schema import load_session_state, save_session_state  # noqa: WPS433

    target = Path(profile_json_path).resolve()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    ss = session_base / "session-state.md"
    session_base.mkdir(parents=True, exist_ok=True)
    if ss.is_file():
        try:
            existing = load_session_state(ss)
            save_session_state(
                ss,
                active_doc=int(existing["active_doc"]),
                profile_path=str(target),
                profile_digest=digest,
                start_id=str(existing["start_id"]),
                holder_finalized=bool(existing["holder_finalized"]),
            )
            return ss
        except ValueError:
            pass
    save_session_state(
        ss,
        active_doc=active_doc,
        profile_path=str(target),
        profile_digest=digest,
        start_id="test",
        holder_finalized=True,
    )
    return ss


def write_profile_pointer(
    project_root: Path,
    cycle_id: str,
    cache_subdir: str,
    profile_json_path: Path,
) -> Path:
    """Bind session-state v2 to a runtime profile path (test/helper)."""
    session_base = session_pointer_path(project_root, cycle_id, cache_subdir).parent
    ss = _write_session_runtime_binding(session_base, profile_json_path)
    data = load_profile_json(Path(profile_json_path).resolve())
    pid = str(data.get("profile_id", "")).strip()
    if pid:
        write_active_profile(project_root, cycle_id, pid)
    return ss


def active_profile_path(project_root: Path, cycle_id: str) -> Path:
    from workflow_common import CACHE_DIR  # noqa: WPS433

    return (
        project_root.resolve()
        / CACHE_DIR
        / cycle_id.strip()
        / ACTIVE_PROFILE_NAME
    )


def write_active_profile(project_root: Path, cycle_id: str, profile_id: str) -> Path:
    """Record the cycle's active compose profile_id (written at start)."""
    path = active_profile_path(project_root, cycle_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile_id.strip() + "\n", encoding="utf-8")
    return path


def read_active_profile(project_root: Path, cycle_id: str) -> str:
    path = active_profile_path(project_root, cycle_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"compose active profile not found: {path}. "
            f"Run stage start with --profile-path first.",
        )
    pid = path.read_text(encoding="utf-8").strip()
    if not pid:
        raise ValueError(f"empty compose active profile: {path}")
    return pid


def resolve_profile_id(
    *,
    project_root: Path | None = None,
    cycle_id: str | None = None,
    revision_dir: Path | None = None,
    explicit: str | None = None,
) -> str:
    """Resolve profile_id: explicit CLI, else cycle context written at start."""
    pid = (explicit or "").strip()
    if pid:
        return pid
    if project_root is not None and (cycle_id or "").strip():
        return read_active_profile(project_root, cycle_id.strip())
    if revision_dir is not None:
        cycle_dir = Path(revision_dir).resolve().parent.parent
        marker = cycle_dir / ACTIVE_PROFILE_NAME
        if not marker.is_file():
            raise FileNotFoundError(
                f"compose active profile not found: {marker}. "
                f"Run stage start with --profile-path first.",
            )
        pid = marker.read_text(encoding="utf-8").strip()
        if not pid:
            raise ValueError(f"empty compose active profile: {marker}")
        return pid
    raise ValueError(
        "profile_id required: run start with --profile-path first",
    )


def read_session_profile_path(session_base: Path) -> Path:
    """Return the runtime profile path bound in session-state.md v2."""
    from session_state_schema import load_session_state  # noqa: WPS433

    ss = Path(session_base) / "session-state.md"
    state = load_session_state(ss)
    resolved = Path(str(state["profile_path"]).strip())
    if not resolved.is_file():
        raise FileNotFoundError(
            f"session-state profile_path missing: {resolved} (from {ss})",
        )
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    expected = str(state["profile_digest"]).strip()
    if digest != expected:
        raise ValueError(
            f"runtime profile digest mismatch for {resolved}: "
            f"got {digest}, session-state has {expected}"
        )
    return resolved


def read_profile_pointer(session_base: Path, project_root: Path) -> Path:
    """Compatibility name: session-state v2 profile_path."""
    del project_root
    return read_session_profile_path(session_base)


def resolve_revision_runtime_profile(
    revision_dir: Path,
    project_root: Path,
    *,
    cycle_id: str | None = None,
) -> RevisionRuntimeProfile:
    """Resolve the session-bound runtime profile owning a revision path.

    ``revision_dir`` must identify ``revisionN`` or ``revisionN/Lx`` beneath the
    nearest ancestor containing ``session-state.md``.
    """
    root = Path(project_root).resolve()
    revision = Path(revision_dir).resolve()

    session_base: Path | None = None
    candidate = revision
    while True:
        ss = candidate / "session-state.md"
        if ss.is_file():
            session_base = candidate
            break
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    if session_base is None:
        raise FileNotFoundError(
            f"session-state.md not found for revision: {revision}",
        )

    relative = revision.relative_to(session_base)
    parts = relative.parts
    valid_revision = bool(
        parts
        and _REVISION_DIR_PATTERN.fullmatch(parts[0])
        and (
            len(parts) == 1
            or (len(parts) == 2 and _SLICE_DIR_PATTERN.fullmatch(parts[1]))
        )
    )
    if not valid_revision:
        raise ValueError(
            "malformed revision path: expected revisionN or revisionN/Lx "
            f"below session base {session_base}, got {relative}",
        )
    revision_root = (session_base / parts[0]).resolve()

    profile_path = read_session_profile_path(session_base)
    profile_data = load_profile_json(profile_path)
    if not isinstance(profile_data, dict):
        raise ValueError(f"compose profile JSON must be an object: {profile_path}")
    raw_profile_id = profile_data.get("profile_id")
    if not isinstance(raw_profile_id, str) or not raw_profile_id.strip():
        raise ValueError(f"compose profile missing nonempty profile_id: {profile_path}")
    profile_id = raw_profile_id.strip()

    if cycle_id is not None:
        cid = cycle_id.strip()
        if not cid:
            raise ValueError("cycle_id must be nonempty when provided")
        active_profile_id = read_active_profile(root, cid)
        if active_profile_id != profile_id:
            raise ValueError(
                "compose active profile mismatch: "
                f"cycle {cid!r} has {active_profile_id!r}, "
                f"session-state has {profile_id!r}",
            )

    return RevisionRuntimeProfile(
        profile_path=profile_path,
        profile_data=profile_data,
        profile_id=profile_id,
        revision_root=revision_root,
        session_base=session_base,
    )


def resolve_compose_session_base(
    project_root: Path,
    cycle_id: str,
    profile_id: str,
) -> Path:
    """Locate session base via cache_subdir + session-state.md."""
    base = compose_session_base(project_root, cycle_id, profile_id)
    ss = base / "session-state.md"
    if not ss.is_file():
        raise FileNotFoundError(
            f"session-state.md not found: {ss}. "
            f"Run stage start with --profile-path first.",
        )
    return base


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
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Load compose profile JSON (session-state v2 or authoring path).

    When ``profile_path`` is set, load that file and skip cycle lookup.
    When ``project_root`` is set and a cycle id is explicit or resolvable from
    env/active-context, session-state.md ``profile_path`` is required (no
    fallback to authoring). Authoring path is used only when ``project_root`` is
    omitted, or when no cycle id can be resolved.
    """
    if profile_path is not None:
        return load_profile_json(Path(profile_path).resolve())
    pid = (profile_id or "").strip()
    if not pid:
        if project_root is None:
            raise ValueError(
                "profile_id required when project_root is omitted",
            )
        root = project_root.resolve()
        cid = (cycle_id or "").strip() or resolve_cycle_id(
            root,
            cycle_id=None,
            conversation_id=conversation_id,
        )
        pid = read_active_profile(root, cid)
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


def read_profile_for_start(profile_json_path: Path) -> dict[str, Any]:
    """Read profile JSON at start; ``profile_id`` comes from the file."""
    data = load_profile_json(profile_json_path.resolve())
    pid = str(data.get("profile_id", "")).strip()
    if not pid:
        raise ValueError("compose-profile.json missing profile_id")
    stage = str(data.get("stage_name", pid)).strip()
    if stage != pid:
        raise ValueError(f"stage_name {stage!r} != profile {pid!r}")
    return data


def validate_compose_profile_path(profile_json_path: Path) -> None:
    """Ensure --profile-path exists; ``profile_id`` is read from the JSON."""
    actual = profile_json_path.resolve()
    if not actual.is_file():
        raise ValueError(f"--profile-path not found: {actual.as_posix()}")


def shell_path(profile: dict[str, Any], key: str) -> Path:
    """Resolve a shell_paths entry relative to WORKFLOW_ROOT."""
    shell_paths = profile.get("shell_paths") or {}
    rel = shell_paths.get(key)
    if not rel:
        raise KeyError(f"shell_paths.{key} missing in profile {profile.get('profile_id')!r}")
    return WORKFLOW_ROOT / rel


def seed_revision_profile_pointer(
    revision_dir: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    *,
    project_root: Path | None = None,
) -> Path:
    """Test helper: bind session-state v2 beside ``revisionN`` and seed L1 ledger."""
    del project_root
    from l_ledger_schema import build_ledger, l_ledger_path, save_l_ledger  # noqa: WPS433

    rev = Path(revision_dir).resolve()
    session_base = rev.parent
    ss = _write_session_runtime_binding(session_base, compose_profile_path(profile_id))
    rev.mkdir(parents=True, exist_ok=True)
    if not l_ledger_path(rev).is_file():
        save_l_ledger(rev, build_ledger(["L1"]))
        (rev / "L1").mkdir(parents=True, exist_ok=True)
    return ss


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
