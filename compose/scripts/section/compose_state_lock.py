"""Durable JSON writes and per-slice Compose mutation locks."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

STATE_LOCK_BASENAME = "_compose-state.lock"


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value into the permit v1 canonical form."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_digest(value: Any) -> str:
    """Return the v1 SHA-256 digest of canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_write_json(path: Path, value: Any) -> None:
    """Write JSON by fsync + replace + parent fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
        _fsync_parent(path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def durable_unlink(path: Path) -> None:
    """Delete an existing file and fsync its parent directory."""
    path.unlink()
    _fsync_parent(path)


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Hold an advisory lock until the context exits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def compose_state_lock(slice_dir: Path) -> Iterator[None]:
    """Serialize all facts / opens read-compute-write transitions in a slice."""
    with exclusive_lock(Path(slice_dir) / STATE_LOCK_BASENAME):
        yield
