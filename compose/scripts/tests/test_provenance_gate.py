#!/usr/bin/env python3
"""Tests for Gate G5 provenance trace schema + gate control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_GATE_CTL = _INDUCTIVE_DIR / "provenance_gate_control.py"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from provenance_trace_schema import (  # noqa: E402
    ROLE_FILES,
    append_delta,
    new_trace,
    validate_delta,
    validate_trace,
)


def _run(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_GATE_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


# --- schema ---------------------------------------------------------------

def _scope_axis1() -> dict:
    return {
        "id": "s1",
        "axis": 1,
        "role": "scope",
        "bucket": "不一致",
        "section": "ST",
        "upstream_anchor": "父级决策X",
        "description": "与X矛盾",
    }


def test_validate_delta_ok():
    assert validate_delta(_scope_axis1(), role="scope") == []


def test_validate_delta_bucket_role_mismatch():
    delta = _scope_axis1()
    delta["bucket"] = "违反"  # norm-constraint bucket, not valid for scope
    errors = validate_delta(delta, role="scope")
    assert any("bucket" in e for e in errors)


def test_validate_delta_axis1_requires_section():
    delta = _scope_axis1()
    delta["section"] = None
    errors = validate_delta(delta, role="scope")
    assert any("section" in e for e in errors)


def test_validate_delta_axis2_forbids_section():
    delta = {
        "id": "i1",
        "axis": 2,
        "role": "intent-baseline",
        "bucket": "未履行意图",
        "section": "ST",
        "upstream_anchor": "意图Y",
        "description": "未履行Y",
    }
    errors = validate_delta(delta, role="intent-baseline")
    assert any("section=null" in e for e in errors)


def test_norm_constraint_has_no_axis2():
    delta = {
        "id": "n1",
        "axis": 2,
        "role": "norm-constraint",
        "bucket": "违反",
        "upstream_anchor": "规范Z",
        "description": "违反Z",
    }
    errors = validate_delta(delta, role="norm-constraint")
    assert any("axis 2" in e for e in errors)


def test_append_delta_rejects_duplicate_id():
    trace = new_trace(role="scope")
    trace = append_delta(trace, _scope_axis1())
    try:
        append_delta(trace, _scope_axis1())
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected duplicate id to raise")


def test_status_forced_pending_signoff():
    trace = new_trace(role="scope")
    delta = _scope_axis1()
    delta["status"] = "signed"
    trace = append_delta(trace, delta)
    assert trace["deltas"][0]["status"] == "pending-signoff"
    assert trace["deltas"][0]["signoff"] is None
    assert validate_trace(trace) == []


# --- control CLI ----------------------------------------------------------

def test_init_creates_three_traces(tmp_path: Path):
    code, payload = _run(tmp_path, "init-session", "--cycle-id", "feat-x", "--stage", "lulu-design")
    assert code == 0, payload
    for fname in ROLE_FILES.values():
        assert (tmp_path / fname).is_file()
    assert (tmp_path / "provenance-gate-state.json").is_file()


def test_init_twice_fails(tmp_path: Path):
    _run(tmp_path, "init-session")
    code, payload = _run(tmp_path, "init-session")
    assert code == 1
    assert "already exists" in payload["error"]


def test_record_and_close_flow(tmp_path: Path):
    _run(tmp_path, "init-session", "--stage", "lulu-design")
    code, payload = _run(
        tmp_path, "record-delta",
        "--role", "scope", "--id", "s1", "--axis", "1", "--bucket", "不一致",
        "--section", "ST", "--upstream-anchor", "X", "--description", "与X矛盾",
    )
    assert code == 0, payload
    code, payload = _run(
        tmp_path, "record-delta",
        "--role", "intent-baseline", "--id", "i1", "--axis", "2", "--bucket", "未履行意图",
        "--upstream-anchor", "Y", "--description", "未履行Y",
    )
    assert code == 0, payload

    code, payload = _run(tmp_path, "gate-close")
    assert code == 0, payload
    assert payload["closed"] == "G5"
    assert payload["total_deltas"] == 2
    assert payload["delta_counts"] == {"intent-baseline": 1, "scope": 1, "norm-constraint": 0}


def test_record_invalid_bucket_rejected(tmp_path: Path):
    _run(tmp_path, "init-session")
    code, payload = _run(
        tmp_path, "record-delta",
        "--role", "scope", "--id", "s1", "--axis", "1", "--bucket", "扩充意图",
        "--section", "ST", "--upstream-anchor", "X", "--description", "d",
    )
    assert code == 1
    assert "bucket" in payload["error"]


def test_record_after_close_rejected(tmp_path: Path):
    _run(tmp_path, "init-session")
    _run(tmp_path, "gate-close")
    code, payload = _run(
        tmp_path, "record-delta",
        "--role", "scope", "--id", "s1", "--axis", "1", "--bucket", "不一致",
        "--section", "ST", "--upstream-anchor", "X", "--description", "d",
    )
    assert code == 1
    assert "closed" in payload["error"]
