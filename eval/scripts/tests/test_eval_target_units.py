#!/usr/bin/env python3
"""Tests for eval_target_units (K3-d — chapter-only units from B)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_target_units as etu  # noqa: E402

_FIXTURE_CHAPTER = """# Title

<!-- chapter:chap-a -->
## Alpha

Prose one.

### Detail

More detail.

---
<!-- chapter:chap-b -->
## Beta

Only beta body.
"""

_FIXTURE_SECTION_KEY_LEGACY = """# Title

## Overview <!-- section-key:OV -->

OV body paragraph.
"""


def test_detect_shape_chapter() -> None:
    assert etu.detect_shape(_FIXTURE_CHAPTER) == "chapter"
    assert etu.detect_shape(_FIXTURE_SECTION_KEY_LEGACY) == "unknown"
    assert etu.detect_shape("# plain\n") == "unknown"


def test_chapter_units_non_empty() -> None:
    view = etu.units_from_eval_target(_FIXTURE_CHAPTER)
    assert view["shape"] == "chapter"
    assert view["empty"] is False
    assert [c["id"] for c in view["containers"]] == ["chap-a", "chap-b"]
    assert len(view["containers"][0]["units"]) >= 1
    assert view["containers"][1]["units"][0]["id"].startswith("chap-b#")
    assert "Only beta body" in view["containers"][1]["units"][0]["text"]


def test_section_key_legacy_is_unknown() -> None:
    view = etu.units_from_eval_target(_FIXTURE_SECTION_KEY_LEGACY)
    assert view["shape"] == "unknown"
    assert view["empty"] is True
    assert view["containers"] == []


def test_prior_units_and_severity_hints() -> None:
    view = etu.units_from_eval_target(_FIXTURE_CHAPTER)
    prior = etu.prior_container_units(view, "chap-b")
    assert prior
    assert all(u["container_id"] == "chap-a" for u in prior)
    hints_a = etu.severity_hints_chapter(view, "chap-a")
    assert hints_a["is_first"] and not hints_a["is_last"] and not hints_a["has_prior"]
    hints_b = etu.severity_hints_chapter(view, "chap-b")
    assert hints_b["is_last"] and hints_b["has_prior"] and not hints_b["before_last"]


def test_sim_tech_doc_fixture_if_present() -> None:
    sim = (
        Path(__file__).resolve().parents[4]
        / ".cache"
        / "plan-init-sim-builders-entry"
        / "revision1"
        / "tech-doc.md"
    )
    if not sim.is_file():
        return
    view = etu.units_from_eval_target(sim.read_text(encoding="utf-8"))
    assert view["shape"] == "chapter"
    assert view["empty"] is False
    assert len(view["containers"]) >= 1


def test_cli_inspect(tmp_path: Path, capsys) -> None:
    path = tmp_path / "doc.md"
    path.write_text(_FIXTURE_CHAPTER, encoding="utf-8")
    assert etu.main(["--path", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["shape"] == "chapter"
    assert payload["empty"] is False


def test_no_compose_private_literals() -> None:
    src = Path(etu.__file__).read_text(encoding="utf-8")
    for banned in ("_facts.json", "_chapters.json", "facts_control", "chapters_control"):
        assert banned not in src
