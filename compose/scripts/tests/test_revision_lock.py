#!/usr/bin/env python3
"""Tests for revision and session advisory locks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import bootstrap  # noqa: F401
import pytest

from revision_lock import (
    LockTimeout,
    acquire_lock,
    cycle_lock,
    revision_lock,
    revision_lock_path,
    session_lock,
)


def test_exclusive_blocks_shared(tmp_path) -> None:
    path = revision_lock_path(tmp_path)
    with revision_lock(tmp_path, exclusive=True):
        with pytest.raises(LockTimeout):
            with acquire_lock(path, exclusive=False, timeout_s=0.2):
                pass


def test_shared_allows_shared(tmp_path) -> None:
    with revision_lock(tmp_path, exclusive=False):
        with acquire_lock(revision_lock_path(tmp_path), exclusive=False, timeout_s=0.5):
            pass


def test_timeout_code(tmp_path) -> None:
    with revision_lock(tmp_path, exclusive=True):
        with pytest.raises(LockTimeout) as exc:
            with revision_lock(tmp_path, exclusive=True, timeout_s=0.15):
                pass
        assert exc.value.code == "lock_timeout"


def test_lock_releases_for_later_exclusive(tmp_path) -> None:
    with revision_lock(tmp_path, exclusive=True):
        pass

    def _hold() -> str:
        with revision_lock(tmp_path, exclusive=True, timeout_s=1.0):
            return "ok"

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(_hold).result() == "ok"


def test_cycle_exclusive_blocks_second_exclusive(tmp_path) -> None:
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    with cycle_lock(cycle, exclusive=True):
        with pytest.raises(LockTimeout):
            with cycle_lock(cycle, exclusive=True, timeout_s=0.15):
                pass


def test_session_shared_allows_revision_exclusive(tmp_path) -> None:
    session = tmp_path / "session"
    revision = session / "revision1"
    revision.mkdir(parents=True)
    with session_lock(session, exclusive=False):
        with revision_lock(revision, exclusive=True, timeout_s=0.5):
            pass
