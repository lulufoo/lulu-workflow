#!/usr/bin/env python3
"""Tests for the inductive Gate 3 frontier-sweep machine.

Covers the frontier_kw state plus the set-frontier / append-to-section /
clear-section subcommands that replaced the one-shot commit-section.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SECTION_CTL = _INDUCTIVE_DIR / "inductive_g3_section_control.py"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from g3_section_pointer_schema import (  # noqa: E402
    FRONTIER_TARGET_DEFAULT,
    init_section_pointer,
    normalize_section_pointer,
    set_frontier,
    validate_section_pointer,
)


def _run(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_SECTION_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _seed(out_dir: Path, active: str = "I") -> None:
    code, payload = _run(out_dir, "init-pointer", "--sections", "I,ST", "--mandatory", "")
    assert code == 0, payload
    code, payload = _run(out_dir, "activate-section", "--section", active)
    assert code == 0, payload


def _blocking_ep_json(section: str) -> str:
    return json.dumps(
        {
            "section": section,
            "block": "blk",
            "method": "impl_gap",
            "kw": "KW1",
            "type": "undecided",
            "description": "a blocking gap",
            "code_refs": [],
            "confidence": "direct",
            "blocking": True,
            "source": "ai_scan",
            "status": "open",
        }
    )


# --- schema layer -----------------------------------------------------------

def test_default_frontier_is_zero():
    ptr = init_section_pointer(coverage_sections=["I", "ST"], mandatory=[], cycle_id="c1")
    assert ptr["sections"]["I"]["frontier_kw"] == 0
    assert validate_section_pointer(ptr) == []


def test_set_frontier_sets_value():
    ptr = init_section_pointer(coverage_sections=["I"], mandatory=[], cycle_id="c1")
    ptr = set_frontier(ptr, "I", 2)
    assert ptr["sections"]["I"]["frontier_kw"] == 2


def test_set_frontier_rejects_out_of_range():
    ptr = init_section_pointer(coverage_sections=["I"], mandatory=[], cycle_id="c1")
    for bad in (-1, 5):
        try:
            set_frontier(ptr, "I", bad)
        except ValueError:
            continue
        raise AssertionError(f"frontier_kw={bad} should have been rejected")


def test_normalize_clamps_frontier():
    raw = {
        "version": "1",
        "coverage_order": ["I"],
        "sections": {"I": {"status": "active", "frontier_kw": 99}},
        "mandatory": [],
        "active_section": "I",
    }
    norm = normalize_section_pointer(raw)
    assert norm["sections"]["I"]["frontier_kw"] == 4


# --- control layer (CLI) ----------------------------------------------------

def test_set_frontier_focus_guard(tmp_path):
    _seed(tmp_path, active="I")
    code, payload = _run(tmp_path, "set-frontier", "--section", "ST", "--kw", "1")
    assert code == 1 and not payload["ok"]
    assert "focus guard" in payload["error"]


def test_status_reports_frontier(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", "2")
    code, payload = _run(tmp_path, "status")
    assert code == 0
    assert payload["frontier"] == {"I": 2, "ST": 0}


def test_append_accumulates_bucket(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "append-to-section", "--section", "I", "--content", "first")
    _run(tmp_path, "append-to-section", "--section", "I", "--content", "second")
    bucket = (tmp_path / "inductive-scope" / "I.md").read_text(encoding="utf-8")
    assert "first" in bucket and "second" in bucket
    assert bucket.index("first") < bucket.index("second")


def test_clear_blocked_by_low_frontier(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "append-to-section", "--section", "I", "--content", "body")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "frontier_kw" in payload["error"]


def test_clear_blocked_by_empty_bucket(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 1 and "empty" in payload["error"]


def test_clear_blocked_by_blocking_open_ep(tmp_path):
    _seed(tmp_path, active="ST")
    _run(tmp_path, "set-frontier", "--section", "ST", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "append-to-section", "--section", "ST", "--content", "body")
    _run(tmp_path, "register-ep", "--json", _blocking_ep_json("ST"))
    code, payload = _run(tmp_path, "clear-section", "--section", "ST")
    assert code == 1 and "blocking open EP" in payload["error"]


def test_clear_succeeds_when_ready(tmp_path):
    _seed(tmp_path, active="I")
    _run(tmp_path, "set-frontier", "--section", "I", "--kw", str(FRONTIER_TARGET_DEFAULT))
    _run(tmp_path, "append-to-section", "--section", "I", "--content", "the I figure")
    code, payload = _run(tmp_path, "clear-section", "--section", "I")
    assert code == 0 and payload["cleared"] == "I"
    code, status = _run(tmp_path, "status")
    assert status["sections"]["I"] == "cleared"
