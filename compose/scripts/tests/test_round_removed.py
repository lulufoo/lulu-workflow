#!/usr/bin/env python3
"""Tests that Round/prober/refiner implementation references are removed."""

from __future__ import annotations

import subprocess
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _WORKFLOW_ROOT.parent
_SELF = Path(__file__).resolve()
_FORBIDDEN = (
    "RoundIteration",
    "begin-round",
    "advance-round",
    "prober-runner",
    "refiner-runner",
    "structural-probe",
    "section_round_control",
    "structural_probe",
    "$ROUND_CONTROL",
)


def test_round_references_removed_from_workflow_files() -> None:
    files = subprocess.check_output(
        ["git", "ls-files"],
        cwd=_WORKFLOW_ROOT,
        text=True,
    ).splitlines()
    violations = []
    for rel in files:
        path = (_WORKFLOW_ROOT / rel).resolve()
        if path == _SELF:
            continue
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN:
            if token in text:
                violations.append(f"{rel}: {token}")
    assert violations == []
