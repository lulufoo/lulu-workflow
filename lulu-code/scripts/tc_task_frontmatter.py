#!/usr/bin/env python3
"""Parse YAML frontmatter from work-order task.md files (stdlib re only)."""

from __future__ import annotations

import re
from pathlib import Path


def read_task_frontmatter(task_path: Path) -> dict:
    """Parse YAML frontmatter from task.md."""
    content = task_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No frontmatter found in {task_path}")
    fm_text = fm_match.group(1)

    result: dict = {}
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        block_match = re.match(r"^(\w+):\s*$", line)
        if block_match:
            key = block_match.group(1)
            nested: dict[str, str] = {}
            i += 1
            while i < len(lines):
                sub = re.match(r"^  (\w+):\s*(.+)", lines[i])
                if sub:
                    nested[sub.group(1)] = sub.group(2).strip()
                    i += 1
                else:
                    break
            result[key] = nested
            continue
        scalar_match = re.match(r"^(\w+):\s*(.+)", line)
        if scalar_match:
            result[scalar_match.group(1)] = scalar_match.group(2).strip().strip('"')
        i += 1
    return result


def parse_tdd_exempt_from_frontmatter(fm: dict) -> bool | None:
    """Return bool if tdd_exempt is set in frontmatter, else None."""
    if "tdd_exempt" not in fm:
        return None
    value = str(fm["tdd_exempt"]).strip().lower()
    return value in ("true", "yes", "1")
