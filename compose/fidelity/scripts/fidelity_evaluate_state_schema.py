#!/usr/bin/env python3
"""Schema I/O for revision-local ``fidelity-evaluate-state.md`` (bypass Evaluating)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_FIDELITY_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE_SCRIPTS = _FIDELITY_SCRIPTS.parents[1] / "scripts"
_CORE = _COMPOSE_SCRIPTS / "core"
for p in (_COMPOSE_SCRIPTS, _CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from workflow_common import parse_frontmatter_fields  # noqa: E402

STATE_FILENAME = "fidelity-evaluate-state.md"
MAX_ROUNDS = 3
STATUSES = frozenset({"pending", "passed", "failed"})


def fidelity_evaluate_state_path(revision_dir: Path) -> Path:
    return revision_dir.resolve() / STATE_FILENAME


def empty_state(*, intake: str = "atomize") -> dict[str, str]:
    return {
        "version": "1",
        "status": "pending",
        "intake": intake,
        "round": "0",
        "max_rounds": str(MAX_ROUNDS),
    }


def load_state(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"missing fidelity state: {path}")
    return parse_frontmatter_fields(path.read_text(encoding="utf-8"))


def save_state(path: Path, data: dict[str, Any]) -> None:
    status = str(data.get("status", "")).strip()
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    ordered = {
        "version": str(data.get("version", "1")),
        "status": status,
        "intake": str(data.get("intake", "atomize")),
        "round": str(data.get("round", "0")),
        "max_rounds": str(data.get("max_rounds", MAX_ROUNDS)),
    }
    lines = ["---"]
    for key, value in ordered.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def gate_allows_derive(data: dict[str, str]) -> bool:
    return str(data.get("status", "")).strip() == "passed"
