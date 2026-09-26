#!/usr/bin/env python3
"""Mechanical archive for superseded approach Working generations."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

_DX = re.compile(r"^D\d+$")
_SNAPSHOTS = (
    "dependency-tree.json",
    "decision-rulers.json",
    "decision-package.json",
    "discussion-pointer.json",
)


def archive_working_generation(approach_root: Path, transaction_id: str) -> Path:
    """Snapshot current metadata and move Dx sessions to a transaction archive."""
    root = Path(approach_root).resolve()
    archive = root / "working-archive" / str(transaction_id).strip()
    archive.mkdir(parents=True, exist_ok=True)
    for name in _SNAPSHOTS:
        source = root / name
        target = archive / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    sessions = archive / "sessions"
    sessions.mkdir(exist_ok=True)
    moved: list[str] = []
    for source in root.iterdir():
        if source.is_dir() and _DX.match(source.name):
            target = sessions / source.name
            if target.exists():
                continue
            source.replace(target)
            moved.append(source.name)
    (archive / "manifest.json").write_text(
        json.dumps({"transaction_id": str(transaction_id), "moved_sessions": moved}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return archive
