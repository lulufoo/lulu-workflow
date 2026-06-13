#!/usr/bin/env python3
"""Tests for round_control.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_control import (  # noqa: E402
    _normalize_section,
    _parse_state_vector,
    round_probe_input,
)

_SCRIPT = Path(__file__).resolve().parent / "round_control.py"
_CYCLE_ID = "test-cycle"


def _setup_cycle(tmp_path: Path) -> Path:
    cycle_dir = tmp_path / _CYCLE_ID
    plan_base = cycle_dir / "tech" / "plan"
    revision = plan_base / "revision1"
    revision.mkdir(parents=True)
    (plan_base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (revision / "tech-doc.md").write_text(
        "---\n\n"
        "<!-- state-vector: NS:L0, NG:L1, KD:L1, SK:L0, T:L1 -->\n\n"
        "## North Star\n\nGoal.\n\n"
        "## Non-Goals & Invariants\n\nNG.\n\n"
        "## Key Decisions\n\nKD.\n\n"
        "## Approach Skeleton\n\nSK.\n\n"
        "## Tasks\n\nT.\n",
        encoding="utf-8",
    )
    (revision / "drafting-progress.md").write_text(
        f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\n"
        "current_step: RoundIteration\nround: 1\n---\n",
        encoding="utf-8",
    )
    return cycle_dir


def _run(cycle_dir: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--cycle-dir", str(cycle_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_parse_state_vector():
    text = "<!-- state-vector: NS:L0, NG:L2, KD:L1, SK:L0, T:L3 -->"
    assert _parse_state_vector(text) == {
        "NS": 0, "NG": 2, "KD": 1, "SK": 0, "T": 3,
    }


def test_parse_state_vector_merges_inv_into_ng():
    text = "<!-- state-vector: NS:L0, NG:L1, INV:L2, KD:L1, SK:L0, T:L1 -->"
    assert _parse_state_vector(text)["NG"] == 2


def test_normalize_section_aliases():
    assert _normalize_section("north star") == "NS"
    assert _normalize_section("KD") == "KD"


def test_read_context(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    ctx = _run(cycle_dir, "read-context")
    assert ctx["state_vector"]["NS"] == 0
    assert ctx["round"] == 1
    assert (cycle_dir / "tech" / "plan" / "anchor-ledger.md").exists()


def test_check_l0(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    result = _run(cycle_dir, "check-l0")
    assert "North Star" in result["l0_sections"]
    assert "Approach Skeleton" in result["l0_sections"]


def test_apply_zoom_and_sign(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "apply-zoom", "--section", "NS", "--from-l", "0", "--to-l", "1", "--round", "1")
    tech_doc = (cycle_dir / "tech" / "plan" / "revision1" / "tech-doc.md").read_text()
    assert "NS:L1" in tech_doc
    assert "<!-- signed: Round 1, L1," in tech_doc


def test_append_skip_rejects_l0(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "append-skip",
            "--section",
            "NS",
            "--probe",
            "P1",
            "--round",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "L0" in proc.stderr


def test_append_skip_empty_notes_roundtrip(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    _run(cycle_dir, "append-skip", "--section", "NG", "--probe", "P2", "--round", "1")
    ctx = _run(cycle_dir, "read-context")
    assert len(ctx["skips"]) == 1
    assert ctx["skips"][0]["probe"] == "P2"


def test_update_anchor_status(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    result = _run(
        cycle_dir,
        "append-anchor",
        "--section",
        "NG",
        "--criterion",
        "must be idempotent",
        "--round",
        "1",
    )
    anchor_id = result["id"]
    _run(cycle_dir, "update-anchor-status", "--id", anchor_id, "--status", "failing")
    ctx = _run(cycle_dir, "read-context")
    assert ctx["anchors"][0]["status"] == "failing"
    conv = _run(cycle_dir, "check-convergence", "--no-accept", "--probes-passed")
    assert conv["converged"] is False
    assert "anchor" in conv["reason"]


def test_check_convergence(tmp_path: Path):
    cycle_dir = _setup_cycle(tmp_path)
    result = _run(cycle_dir, "check-convergence", "--no-accept", "--probes-passed")
    assert result["converged"] is False
    assert "L0" in result["reason"]


class TestRoundProbeInput:
    def test_returns_dispatch_input_in_round_iteration(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        revision = cycle_dir / "tech" / "plan" / "revision1"
        result = round_probe_input(cycle_dir)
        assert result["ok"] is True
        assert "dispatch_input" in result
        inp = result["dispatch_input"]
        assert f"CYCLE_ID:       {_CYCLE_ID}" in inp
        assert "CYCLE_TYPE:     feature" in inp
        assert "ROUND_N:        1" in inp
        assert revision.resolve().as_posix() in inp
        assert "tech-doc.md" in inp

    def test_round_2_reflects_advanced_round(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\n"
            "current_step: RoundIteration\nround: 2\n---\n",
            encoding="utf-8",
        )
        result = round_probe_input(cycle_dir)
        assert result["ok"] is True
        assert "ROUND_N:        2" in result["dispatch_input"]

    def test_fails_when_ready_not_round_iteration(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\ncurrent_step: Ready\n---\n",
            encoding="utf-8",
        )
        result = round_probe_input(cycle_dir)
        assert result["ok"] is False
        assert "RoundIteration" in result["reason"]

    def test_fails_without_progress(self, tmp_path: Path):
        cycle_dir = tmp_path / "empty-cycle"
        plan_base = cycle_dir / "tech" / "plan"
        revision = plan_base / "revision1"
        revision.mkdir(parents=True)
        (plan_base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        result = round_probe_input(cycle_dir)
        assert result["ok"] is False

    def test_cli_plaintext_stdout(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        revision = cycle_dir / "tech" / "plan" / "revision1"
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "round-probe-input",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.startswith("CYCLE_DIR:")
        assert f"CYCLE_ID:       {_CYCLE_ID}" in proc.stdout
        assert "ROUND_N:        1" in proc.stdout
        assert revision.resolve().as_posix() in proc.stdout
        try:
            json.loads(proc.stdout)
            raise AssertionError("expected plain-text stdout, not JSON")
        except json.JSONDecodeError:
            pass

    def test_cli_failure_json_stdout(self, tmp_path: Path):
        cycle_dir = _setup_cycle(tmp_path)
        progress = cycle_dir / "tech" / "plan" / "revision1" / "drafting-progress.md"
        progress.write_text(
            f"---\nversion: 1\ncycle_id: {_CYCLE_ID}\ncurrent_step: Ready\n---\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "round-probe-input",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False
