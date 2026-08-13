#!/usr/bin/env python3
"""Cycle-level delivered-refs.json I/O (shared Layer A)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_schema import detect_platform
from platforms.paths import cache_dir

_FILE_NAME = "delivered-refs.json"
_VERSION = 1
COMPOSE_ARTIFACT = "compose-package"
_COMPOSE_EQUALITY_KEYS = (
    "delivered_type",
    "profile_id",
    "revision",
    "path",
    "artifact",
    "package_digest",
    "source_workflow_state",
)
_COMPOSE_ALLOWED_KEYS = frozenset(_COMPOSE_EQUALITY_KEYS + ("delivered_at",))


class DeliveryInconsistent(ValueError):
    """Same delivered_type exists with a different equality payload."""

    def __init__(self, delivered_type: str) -> None:
        super().__init__(
            f"delivery_inconsistent: existing {delivered_type} payload differs"
        )
        self.code = "delivery_inconsistent"
        self.delivered_type = delivered_type


def _cache_dir() -> Path:
    return cache_dir(detect_platform())


def delivered_refs_file_path(cycle_id: str, project_root: Path) -> Path:
    return (project_root / _cache_dir() / cycle_id / _FILE_NAME).resolve()


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _empty_file_payload() -> dict[str, Any]:
    return {"version": _VERSION, "entries": {}}


def _durable_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
        parent_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def load_delivered_refs_file(cycle_id: str, project_root: Path) -> dict[str, Any]:
    path = delivered_refs_file_path(cycle_id, project_root)
    if not path.is_file():
        return _empty_file_payload()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid delivered-refs.json (not object): {path}")
    entries = data.get("entries")
    if entries is None:
        data["entries"] = {}
    elif not isinstance(entries, dict):
        raise ValueError(f"invalid delivered-refs.json entries: {path}")
    return data


def save_delivered_refs_file(cycle_id: str, project_root: Path, data: dict[str, Any]) -> Path:
    path = delivered_refs_file_path(cycle_id, project_root)
    payload = dict(data)
    payload["version"] = _VERSION
    _durable_write_json(path, payload)
    return path


def compose_equality_projection(entry: dict[str, Any]) -> dict[str, Any]:
    extra = set(entry) - _COMPOSE_ALLOWED_KEYS
    if extra:
        raise ValueError(
            f"compose delivered-ref extra fields not allowed: {sorted(extra)}"
        )
    out: dict[str, Any] = {}
    for key in _COMPOSE_EQUALITY_KEYS:
        if key not in entry:
            raise ValueError(f"compose delivered-ref missing {key}")
        out[key] = entry[key]
    return out


def _compose_payload(
    *,
    delivered_type: str,
    path: str,
    revision: int | str,
    profile_id: str,
    source_workflow_state: str,
    package_digest: str,
) -> dict[str, Any]:
    return {
        "delivered_type": delivered_type,
        "path": str(Path(path).resolve()),
        "revision": revision,
        "profile_id": profile_id,
        "artifact": COMPOSE_ARTIFACT,
        "package_digest": package_digest,
        "source_workflow_state": source_workflow_state,
    }


def record_delivered_ref(
    cycle_id: str,
    project_root: Path,
    *,
    delivered_type: str,
    path: str,
    revision: int | str,
    profile_id: str,
    source_workflow_state: str,
    artifact: str | None = None,
    package_digest: str | None = None,
) -> dict[str, Any]:
    """Upsert one stage entry in {cycle_id}/delivered-refs.json.

    Compose entries (``artifact=compose-package``) require ``package_digest``
    and use equality projection (``delivered_at`` excluded). Exact retry is a
    no-op; a different payload raises ``DeliveryInconsistent``.
    """
    dtype = delivered_type.strip()
    if not dtype:
        raise ValueError("delivered_type must be non-empty")
    artifact_s = str(artifact or "").strip()
    data = load_delivered_refs_file(cycle_id, project_root)
    entries = dict(data.get("entries") or {})
    existing = entries.get(dtype)

    if artifact_s == COMPOSE_ARTIFACT:
        digest = str(package_digest or "").strip()
        if not digest:
            raise ValueError("compose delivered-ref requires package_digest")
        expected = _compose_payload(
            delivered_type=dtype,
            path=path,
            revision=revision,
            profile_id=profile_id,
            source_workflow_state=source_workflow_state,
            package_digest=digest,
        )
        if isinstance(existing, dict):
            current = compose_equality_projection(existing)
            if current != expected:
                raise DeliveryInconsistent(dtype)
            return {"ok": True, "reused": True, "entry": existing}
        entry = dict(expected)
        entry["delivered_at"] = datetime.now(timezone.utc).isoformat()
        entries[dtype] = entry
        entries.pop(f"{dtype}-facts", None)
        data["entries"] = entries
        save_delivered_refs_file(cycle_id, project_root, data)
        return {"ok": True, "reused": False, "entry": entry}

    entry = {
        "delivered_type": dtype,
        "path": str(Path(path).resolve()),
        "revision": revision,
        "profile_id": profile_id,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "source_workflow_state": source_workflow_state,
    }
    if artifact_s:
        entry["artifact"] = artifact_s
    if package_digest:
        entry["package_digest"] = str(package_digest).strip()
    entries[dtype] = entry
    entries.pop(f"{dtype}-facts", None)
    data["entries"] = entries
    save_delivered_refs_file(cycle_id, project_root, data)
    return {"ok": True, "reused": False, "entry": entry}


def remove_delivered_ref(
    cycle_id: str,
    project_root: Path,
    delivered_type: str,
) -> bool:
    """Remove one stage entry. Idempotent no-op when missing. Returns True if removed."""
    dtype = delivered_type.strip()
    if not dtype:
        raise ValueError("delivered_type must be non-empty")
    data = load_delivered_refs_file(cycle_id, project_root)
    entries = dict(data.get("entries") or {})
    if dtype not in entries and f"{dtype}-facts" not in entries:
        return False
    entries.pop(dtype, None)
    entries.pop(f"{dtype}-facts", None)
    data["entries"] = entries
    save_delivered_refs_file(cycle_id, project_root, data)
    return True
