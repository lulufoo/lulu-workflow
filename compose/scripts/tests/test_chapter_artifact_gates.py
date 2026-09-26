#!/usr/bin/env python3
"""Tests for chapter write hard gate (non-empty body; no derive / structure probe)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parents[1] / "writing"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from chapter_artifact_gates import check_chapter_write_artifacts  # noqa: E402


def test_check_chapter_write_artifacts_happy(tmp_path: Path):
    cid = "A01-AR"
    (tmp_path / f"_body-{cid}.txt").write_text("body prose\n", encoding="utf-8")
    assert check_chapter_write_artifacts(tmp_path, cid) == []


def test_check_chapter_write_artifacts_rejects_empty_body(tmp_path: Path):
    cid = "A01-AR"
    (tmp_path / f"_body-{cid}.txt").write_text("  \n", encoding="utf-8")
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert any("empty body" in e for e in errs)


def test_check_chapter_write_artifacts_rejects_missing_body(tmp_path: Path):
    cid = "A01-AR"
    errs = check_chapter_write_artifacts(tmp_path, cid)
    assert any("missing body" in e for e in errs)


def test_check_chapter_write_artifacts_ignores_derive(tmp_path: Path):
    """Derive presence/absence is not gated."""
    cid = "A01-AR"
    (tmp_path / f"_body-{cid}.txt").write_text("body\n", encoding="utf-8")
    assert check_chapter_write_artifacts(tmp_path, cid) == []
    (tmp_path / f"_derive-{cid}.json").write_text("{}", encoding="utf-8")
    assert check_chapter_write_artifacts(tmp_path, cid) == []
