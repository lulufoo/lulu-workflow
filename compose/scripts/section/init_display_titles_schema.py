#!/usr/bin/env python3
"""Schema and I/O for revision-dir _title-display.json (section_key → display title)."""

from __future__ import annotations

from pathlib import Path

from _title_map_io import get_title, load_map, save_map, set_title, validate_flat_string_map
from init_artifact_paths import DISPLAY_TITLES_BASENAME, display_titles_path

__all__ = [
    "DISPLAY_TITLES_BASENAME",
    "display_titles_path",
    "get_display_title",
    "load_display_titles",
    "save_display_titles",
    "set_display_title",
    "validate_display_titles",
]


def validate_display_titles(data: object) -> list[str]:
    return validate_flat_string_map(data, label=DISPLAY_TITLES_BASENAME)


def load_display_titles(path: Path) -> dict[str, str]:
    return load_map(path)


def save_display_titles(path: Path, data: dict[str, str]) -> None:
    save_map(path, data)


def get_display_title(data: dict[str, str], section_key: str) -> str:
    return get_title(data, section_key)


def set_display_title(
    revision_dir: Path,
    section_key: str,
    title: str,
) -> Path:
    path = display_titles_path(revision_dir)
    current = load_map(path) if path.is_file() else {}
    updated = set_title(current, section_key, title)
    save_map(path, updated)
    return path
