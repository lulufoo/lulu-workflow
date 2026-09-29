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


TASK_KINDS = ("coding", "action")
EFFECT_KINDS = ("read_only", "mutates")
_CRITERION_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.+?)\s*$")


def parse_kind_from_frontmatter(fm: dict) -> str:
    """Return coding or action. Unknown or missing values become coding."""
    kind = str(fm.get("kind", "coding")).strip()
    if kind in TASK_KINDS:
        return kind
    return "coding"


def parse_mutates_targets(fm: dict) -> list[str]:
    """Return the external systems named by ``mutates: [a, b]``."""
    raw = str(fm.get("mutates", "")).strip().strip("[]")
    return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]


def validate_effects(task_id: str, fm: dict) -> list[str]:
    """Return errors for the effects declaration of an action task."""
    effects = str(fm.get("effects", "")).strip()
    if effects not in EFFECT_KINDS:
        return [f"{task_id}: effects must be one of {list(EFFECT_KINDS)}, got '{effects}'"]
    targets = parse_mutates_targets(fm)
    if effects == "mutates" and not targets:
        return [f"{task_id}: effects mutates requires a non-empty mutates list"]
    if effects == "read_only" and targets:
        return [f"{task_id}: effects read_only must not declare mutates targets"]
    return []


def describe_effects(fm: dict) -> str:
    """Return ``read_only`` or ``mutates: a, b`` for receipts."""
    effects = str(fm.get("effects", "")).strip()
    if effects == "mutates":
        return "mutates: " + ", ".join(parse_mutates_targets(fm))
    return effects


def parse_acceptance_criteria(task_md: str) -> list[str]:
    """Return checklist items under the Section 1 heading of task.md."""
    criteria: list[str] = []
    in_section = False
    for line in task_md.splitlines():
        if line.startswith("## "):
            in_section = line.startswith("## Section 1")
            continue
        if in_section:
            match = _CRITERION_RE.match(line)
            if match:
                criteria.append(match.group(1))
    return criteria


def parse_tdd_exempt_from_frontmatter(fm: dict) -> bool | None:
    """Return bool if tdd_exempt is set in frontmatter, else None."""
    if "tdd_exempt" not in fm:
        return None
    value = str(fm["tdd_exempt"]).strip().lower()
    return value in ("true", "yes", "1")
