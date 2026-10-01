"""Revision- and session-level advisory locks for Compose ledger mutations.

Lock order is cycle → session → revision → slice. This module owns session
and revision locks. Reverse acquisition is forbidden at the call site.
"""

from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SESSION_LOCK_NAME = "_compose-session.lock"
REVISION_LOCK_NAME = "_compose-revision.lock"
CYCLE_LOCK_NAME = "_workflow-cycle.lock"
DEFAULT_TIMEOUT_S = 5.0
_POLL_S = 0.05


class LockTimeoutError(TimeoutError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"lock_timeout: {path}")
        self.path = path
        self.code = "lock_timeout"


def session_lock_path(session_dir: Path) -> Path:
    return Path(session_dir) / SESSION_LOCK_NAME


def revision_lock_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / REVISION_LOCK_NAME


def cycle_lock_path(cycle_cache_dir: Path) -> Path:
    return Path(cycle_cache_dir) / CYCLE_LOCK_NAME


@contextmanager
def acquire_lock(
    path: Path,
    *,
    exclusive: bool,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Iterator[None]:
    """Bounded flock. ``exclusive=True`` is LOCK_EX, else LOCK_SH."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    deadline = time.monotonic() + timeout_s
    with path.open("a+", encoding="utf-8") as stream:
        fd = stream.fileno()
        while True:
            try:
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(path) from exc
                time.sleep(_POLL_S)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def session_lock(
    session_dir: Path,
    *,
    exclusive: bool,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Iterator[None]:
    with acquire_lock(
        session_lock_path(session_dir),
        exclusive=exclusive,
        timeout_s=timeout_s,
    ):
        yield


@contextmanager
def revision_lock(
    revision_dir: Path,
    *,
    exclusive: bool,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Iterator[None]:
    with acquire_lock(
        revision_lock_path(revision_dir),
        exclusive=exclusive,
        timeout_s=timeout_s,
    ):
        yield


@contextmanager
def cycle_lock(
    cycle_cache_dir: Path,
    *,
    exclusive: bool,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Iterator[None]:
    with acquire_lock(
        cycle_lock_path(cycle_cache_dir),
        exclusive=exclusive,
        timeout_s=timeout_s,
    ):
        yield
