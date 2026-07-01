#!/usr/bin/env python3
"""Path helpers for Initializing revision-dir artifacts."""

from __future__ import annotations

from pathlib import Path

DERIVE_PREFIX = "_derive-"
BODY_PREFIX = "_body-"
DISPLAY_TITLES_BASENAME = "_title-display.json"
BLOCK_TITLES_BASENAME = "_title-block.json"


def derive_path(revision_dir: Path, section_key: str) -> Path:
    key = section_key.strip().upper()
    return revision_dir / f"{DERIVE_PREFIX}{key}.json"


def body_path(revision_dir: Path, section_key: str) -> Path:
    key = section_key.strip().upper()
    return revision_dir / f"{BODY_PREFIX}{key}.txt"


def display_titles_path(revision_dir: Path) -> Path:
    return revision_dir / DISPLAY_TITLES_BASENAME


def block_titles_path(revision_dir: Path) -> Path:
    return revision_dir / BLOCK_TITLES_BASENAME
