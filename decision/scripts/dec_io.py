#!/usr/bin/env python3
"""Atomic file I/O helpers for decision session artifacts."""

from __future__ import annotations

from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)
