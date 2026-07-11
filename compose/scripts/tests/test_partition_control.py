#!/usr/bin/env python3
"""Tests for partition_schema / partition_control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from partition_schema import (  # noqa: E402
    filter_i_star,
    save_partition,
    validate_partition_atoms,
)

_CTL = _SECTION / "partition_control.py"


def test_validate_accepts_contiguous_atoms():
    atoms = [
        {"id": "A-1", "text": "one", "home": "CTX"},
        {"id": "A-2", "text": "two", "home": "I"},
    ]
    assert validate_partition_atoms(atoms, allowed_homes=["CTX", "I"]) == []


def test_validate_rejects_bad_id_and_extra_fields():
    atoms = [{"id": "B-1", "text": "x", "home": "CTX", "kind": "nope"}]
    errors = validate_partition_atoms(atoms, allowed_homes=["CTX"])
    assert any("A-<n>" in e for e in errors)
    assert any("unexpected fields" in e for e in errors)


def test_filter_i_star_joins_home(tmp_path: Path):
    atoms = [
        {"id": "A-1", "text": "alpha", "home": "CTX"},
        {"id": "A-2", "text": "beta", "home": "I"},
        {"id": "A-3", "text": "gamma", "home": "CTX"},
    ]
    path = tmp_path / "_partition.json"
    save_partition(path, atoms, allowed_homes=["CTX", "I"])
    prose = filter_i_star(
        json.loads(path.read_text(encoding="utf-8")),
        "CTX",
    )
    assert prose == "alpha\n\ngamma"


def test_control_write_and_filter(tmp_path: Path):
    atoms = [
        {"id": "A-1", "text": "fact one", "home": "GO"},
        {"id": "A-2", "text": "fact two", "home": "AR"},
    ]
    atoms_file = tmp_path / "atoms.json"
    atoms_file.write_text(json.dumps(atoms), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--atoms-file",
            str(atoms_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    assert (rev / "_partition.json").is_file()

    filt = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "filter-i-star",
            "--revision-dir",
            str(rev),
            "--section",
            "GO",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert filt.returncode == 0, filt.stderr
    assert filt.stdout.strip() == "fact one"
