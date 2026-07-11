#!/usr/bin/env python3
"""Tests for i_star_control.resolve-i-star."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scope"))

from i_star_control import resolve_i_star_text  # noqa: E402
from partition_schema import save_partition  # noqa: E402

_CTL = _SECTION / "i_star_control.py"


def _write_section_json(indir: Path, key: str, texts: list[str]) -> None:
    indir.mkdir(parents=True, exist_ok=True)
    decisions = [
        {
            "id": f"{key}-d{i}",
            "kw": i,
            "text": text,
            "trigger": "seed",
            "means": "scope",
            "confidence": "direct",
        }
        for i, text in enumerate(texts, start=1)
    ]
    (indir / f"{key}.json").write_text(
        json.dumps(
            {
                "key": key,
                "status": "cleared",
                "frontier_kw": len(texts),
                "decisions": decisions,
                "open": [],
                "deferred": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_resolve_partition_path_when_inductive_false(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    save_partition(
        rev / "_partition.json",
        [
            {"id": "A-1", "text": "from partition", "home": "CTX"},
            {"id": "A-2", "text": "other", "home": "GO"},
        ],
        allowed_homes=["CTX", "GO"],
    )
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="CTX",
        profile_id="lulu-plan",
        project_root=tmp_path,
    )
    assert err is None
    assert prose == "from partition"


def test_resolve_inductive_when_inductive_true(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    # leftover partition must be ignored
    save_partition(
        rev / "_partition.json",
        [{"id": "A-1", "text": "should ignore", "home": "ST"}],
        allowed_homes=["ST"],
    )
    indir = rev / "inductive-scope"
    _write_section_json(indir, "ST", ["from inductive"])
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="ST",
        profile_id="lulu-design",
        project_root=tmp_path,
        inductive_dir=indir,
    )
    assert err is None
    assert "from inductive" in prose
    assert "should ignore" not in prose


def test_resolve_fails_without_partition_when_inductive_false(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="CTX",
        profile_id="lulu-plan",
        project_root=tmp_path,
    )
    assert prose == ""
    assert err is not None
    assert "partition file not found" in err


def test_resolve_fails_without_inductive_dir_when_true(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="ST",
        profile_id="lulu-design",
        project_root=tmp_path,
        inductive_dir=None,
    )
    assert prose == ""
    assert err is not None
    assert "inductive-dir" in err


def test_empty_section_is_success(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    save_partition(
        rev / "_partition.json",
        [{"id": "A-1", "text": "only go", "home": "GO"}],
        allowed_homes=["CTX", "GO"],
    )
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="CTX",
        profile_id="lulu-plan",
        project_root=tmp_path,
    )
    assert err is None
    assert prose == ""


def test_inductive_missing_section_json_is_empty_success(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    indir = rev / "inductive-scope"
    indir.mkdir()
    _write_section_json(indir, "ST", ["present"])
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="GO",
        profile_id="lulu-design",
        project_root=tmp_path,
        inductive_dir=indir,
    )
    assert err is None
    assert prose == ""


def test_inductive_empty_decisions_is_empty_success(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    indir = rev / "inductive-scope"
    _write_section_json(indir, "ST", [])
    prose, err = resolve_i_star_text(
        revision_dir=rev,
        section="ST",
        profile_id="lulu-design",
        project_root=tmp_path,
        inductive_dir=indir,
    )
    assert err is None
    assert prose == ""


def test_cli_resolve_i_star(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    save_partition(
        rev / "_partition.json",
        [{"id": "A-1", "text": "cli fact", "home": "GO"}],
        allowed_homes=["GO"],
    )
    result = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "resolve-i-star",
            "--revision-dir",
            str(rev),
            "--section",
            "GO",
            "--profile",
            "lulu-plan",
            "--project-root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cli fact"
