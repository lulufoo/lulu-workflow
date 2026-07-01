#!/usr/bin/env python3
"""Schema and I/O for revision-dir _title-block.json (block_key → reader H2 title)."""

from __future__ import annotations

from pathlib import Path

from _title_map_io import get_title, load_map, save_map, set_title, validate_flat_string_map
from init_artifact_paths import BLOCK_TITLES_BASENAME, block_titles_path

__all__ = [
    "BLOCK_TITLES_BASENAME",
    "block_titles_path",
    "get_block_title",
    "load_block_titles",
    "save_block_titles",
    "set_block_title",
    "validate_block_titles",
]


def validate_block_titles(data: object) -> list[str]:
    return validate_flat_string_map(data, label=BLOCK_TITLES_BASENAME)


def load_block_titles(path: Path) -> dict[str, str]:
    return load_map(path)


def save_block_titles(path: Path, data: dict[str, str]) -> None:
    save_map(path, data)


def get_block_title(data: dict[str, str], block_key: str) -> str:
    return get_title(data, block_key)


def set_block_title(
    revision_dir: Path,
    block_key: str,
    title: str,
) -> Path:
    path = block_titles_path(revision_dir)
    current = load_map(path) if path.is_file() else {}
    updated = set_title(current, block_key, title)
    save_map(path, updated)
    return path
