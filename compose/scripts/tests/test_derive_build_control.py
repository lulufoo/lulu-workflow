#!/usr/bin/env python3
"""Tests for derive-runner derive_build_control context gate."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_CTL = (
    Path(__file__).resolve().parents[2]
    / "deductive-runner"
    / "derive-runner"
    / "scripts"
    / "derive_build_control.py"
)


def _load_ctl():
    spec = importlib.util.spec_from_file_location("derive_build_control", _CTL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_context_help():
    proc = subprocess.run(
        [sys.executable, str(_CTL), "context", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "intake-eval" in (proc.stdout or "").lower() or "context" in (proc.stdout or "")


def test_context_fails_without_eval_gate(tmp_path: Path):
    mod = _load_ctl()
    rev = tmp_path / "rev"
    rev.mkdir()
    ns = type(
        "Args",
        (),
        {
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "profile": "plan",
            "cycle_id": "",
        },
    )()
    code = mod.cmd_context(ns)
    assert code != 0


def test_context_fails_when_eval_not_done(tmp_path: Path):
    mod = _load_ctl()
    rev = tmp_path / "rev"
    gate = rev / "fact-intake-eval"
    gate.mkdir(parents=True)
    (gate / "evaluate-state.md").write_text(
        "eval_status: running\n",
        encoding="utf-8",
    )
    ns = type(
        "Args",
        (),
        {
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "profile": "plan",
            "cycle_id": "",
        },
    )()
    code = mod.cmd_context(ns)
    assert code != 0
