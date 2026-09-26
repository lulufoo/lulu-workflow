#!/usr/bin/env python3
"""Contract-layer residue scan: no Split / L-chain / slices after the hard cut."""

from __future__ import annotations

import re
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _WORKFLOW_ROOT / "compose"
_FORBIDDEN = (
    "leave-split",
    "$L_SHELL",
    "$L_STEP",
    "l-chain.md",
    "l-ledger.json",
    "l_ledger_schema",
    "l_shell_control",
    "l_step_control",
    "l_transition_kernel",
)
_L_ID = re.compile(r"\bL\d+\b")
_CONTRACT_ROOTS = (
    _COMPOSE / "SKILL.md",
    _COMPOSE / "references",
    _COMPOSE / "transitions",
    _COMPOSE / "scripts" / "schema",
    _COMPOSE / "scripts" / "session",
    _COMPOSE / "scripts" / "scope",
)


def _iter_contract_files() -> list[Path]:
    files: list[Path] = []
    for root in _CONTRACT_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"})
    return files


def test_contract_layer_drops_split_and_l_chain() -> None:
    for path in _iter_contract_files():
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN:
            assert token not in text, f"{path.relative_to(_WORKFLOW_ROOT)} still has {token!r}"


def test_contract_layer_drops_l_ids_and_slices() -> None:
    skip = {"test_single_input_residue.py"}
    for path in _iter_contract_files():
        if path.name in skip:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py" and "slices" in text:
            # schema tests live under scripts/tests, not this scan.
            rel = path.relative_to(_WORKFLOW_ROOT).as_posix()
            if "/schema/" in rel or "/session/" in rel or "/scope/" in rel:
                assert "slices" not in text, f"{rel} still mentions slices"
        if path.suffix in {".md", ".json"}:
            match = _L_ID.search(text)
            assert match is None, f"{path.relative_to(_WORKFLOW_ROOT)} still has {match.group(0)!r}"
