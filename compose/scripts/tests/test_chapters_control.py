#!/usr/bin/env python3
"""Tests for chapters_control.py CLI (fact-first display layer, M2, not wired)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

_CTL = _SECTION / "chapters_control.py"


def _chapter(cid, anchors, facts, *, op="keep", derived=None):
    return {
        "id": cid,
        "anchor_lenses": anchors,
        "derived_from": derived if derived is not None else [f"cand-{cid}"],
        "op": op,
        "facts": facts,
    }


def test_control_write_validate_status(tmp_path: Path):
    chapters = [
        _chapter(
            "chap-1",
            ["AR"],
            [{"fid": "F-1", "form_lens": "AR"}, {"fid": "F-2", "form_lens": "AR"}],
        ),
        _chapter("chap-2", ["GO"], [], op="drop"),
    ]
    chapters_file = tmp_path / "chapters.json"
    chapters_file.write_text(json.dumps(chapters), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--chapters-file",
            str(chapters_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    assert (rev / "_chapters.json").is_file()
    payload = json.loads(write.stdout)
    assert payload["chapters_total"] == 2
    assert payload["by_op"] == {"keep": 1, "drop": 1}
    assert payload["facts_placed_total"] == 2

    validate = subprocess.run(
        [sys.executable, str(_CTL), "validate", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, validate.stderr
    validate_payload = json.loads(validate.stdout)
    assert validate_payload["chapters_total"] == 2

    status = subprocess.run(
        [sys.executable, str(_CTL), "status", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["exists"] is True
    assert status_payload["chapters_total"] == 2


def test_control_status_missing_file(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    status = subprocess.run(
        [sys.executable, str(_CTL), "status", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["exists"] is False


def test_control_write_rejects_invalid_chapters(tmp_path: Path):
    bad = [_chapter("chap-1", ["AR"], [])]  # rendered chapter with zero facts
    chapters_file = tmp_path / "chapters.json"
    chapters_file.write_text(json.dumps(bad), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--chapters-file",
            str(chapters_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 1
    assert "L4 no-empty-rendered-chapter" in write.stderr


def test_control_write_lowercase_lenses_are_normalized(tmp_path: Path):
    lower = [_chapter("chap-1", ["ar"], [{"fid": "F-1", "form_lens": "ar"}])]
    chapters_file = tmp_path / "chapters.json"
    chapters_file.write_text(json.dumps(lower), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--chapters-file",
            str(chapters_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    saved = json.loads((rev / "_chapters.json").read_text(encoding="utf-8"))
    assert saved[0]["anchor_lenses"] == ["AR"]
    assert saved[0]["facts"][0]["form_lens"] == "AR"
