#!/usr/bin/env python3
"""Session-scoped external path allowlist for externalPathGuard.sessionAllow.

Collects user-mentioned external paths (files or directories, existing or not)
and allows exact or prefix matches for the rest of the session.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Set

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402

_ABSOLUTE_PATH_RE = re.compile(
    r"/(?:Users|tmp|var|etc|opt|home)(?:/[^\s\)'\"`,<>]+)+"
)
_TILDE_PATH_RE = re.compile(r"~(?:/[^\s\)'\"`,<>]+)+")
_TRAILING_PUNCT = ".,;:!?)\"'`"


def session_paths_root(platform: str = "cursor") -> Path:
    return Path.cwd() / platform_cache_dir(platform) / "session-paths"


def normalize_candidate(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def _strip_trailing_punct(path_str: str) -> str:
    return path_str.rstrip(_TRAILING_PUNCT)


def extract_paths_from_prompt(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for pattern in (_ABSOLUTE_PATH_RE, _TILDE_PATH_RE):
        for match in pattern.finditer(text):
            candidate = _strip_trailing_punct(match.group(0))
            if candidate:
                found.append(candidate)
    return found


def extract_paths_from_attachments(attachments: object) -> list[str]:
    if not isinstance(attachments, list):
        return []
    paths: list[str] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "file":
            continue
        raw = item.get("file_path") or item.get("filePath") or ""
        if isinstance(raw, str) and raw.strip():
            paths.append(raw.strip())
    return paths


def is_eligible_path(path: Path, workspace_root: Path) -> bool:
    """True when path is outside the workspace (file or directory; may not exist yet)."""
    try:
        path.relative_to(workspace_root)
        return False
    except ValueError:
        return True


def _session_file(session_id: str, platform: str) -> Path:
    safe_id = session_id.strip() or "unknown"
    root = session_paths_root(platform)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe_id}.json"


def load_session_paths(session_id: str, platform: str = "cursor") -> Set[str]:
    state_file = session_paths_root(platform) / f"{(session_id.strip() or 'unknown')}.json"
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    raw_paths = data.get("paths") if isinstance(data, dict) else None
    if not isinstance(raw_paths, list):
        return set()
    resolved: Set[str] = set()
    for entry in raw_paths:
        if not isinstance(entry, str) or not entry.strip():
            continue
        try:
            resolved.add(str(normalize_candidate(entry)))
        except OSError:
            continue
    return resolved


def add_session_paths(
    session_id: str,
    paths: Iterable[str],
    *,
    platform: str = "cursor",
) -> None:
    if not paths:
        return
    existing = load_session_paths(session_id, platform)
    merged = set(existing)
    for path_str in paths:
        if not path_str:
            continue
        try:
            merged.add(str(normalize_candidate(path_str)))
        except OSError:
            continue
    if merged == existing:
        return
    state_file = _session_file(session_id, platform)
    payload = {
        "paths": sorted(merged),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def is_session_allowed(
    path_str: str,
    session_id: str,
    platform: str = "cursor",
) -> bool:
    if not path_str or not path_str.strip():
        return False
    try:
        target = normalize_candidate(path_str)
    except OSError:
        return False
    allowed = load_session_paths(session_id, platform)
    target_key = str(target)
    if target_key in allowed:
        return True
    for entry in allowed:
        try:
            target.relative_to(Path(entry))
            return True
        except ValueError:
            continue
    return False


def collect_eligible_paths(
    *,
    prompt: str,
    attachments: object,
    workspace_root: Path,
) -> list[str]:
    candidates = extract_paths_from_prompt(prompt) + extract_paths_from_attachments(
        attachments
    )
    eligible: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = normalize_candidate(candidate)
        except OSError:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if is_eligible_path(resolved, workspace_root):
            eligible.append(key)
    return eligible


def cleanup_old_session_files(root: Path, days: int = 7) -> None:
    try:
        if not root.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for state_file in root.iterdir():
            if not state_file.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(
                    state_file.stat().st_mtime, tz=timezone.utc
                )
                if mtime < cutoff:
                    state_file.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass
