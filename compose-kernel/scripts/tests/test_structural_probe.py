#!/usr/bin/env python3
"""Tests for structural_probe.py and mechanical_fixer.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
from mechanical_fixer import EXIT_DEGRADE, apply_mechanical_fix  # noqa: E402
from structural_probe import run_structural_probe  # noqa: E402
from test_registry_fixtures import first_section_key  # noqa: E402
from test_registry_fixtures import minimal_compose_doc_markdown, section_headings_map  # noqa: E402

_CRITERIA = (
    Path(__file__).resolve().parents[3]
    / "tech-design"
    / "structural-probe-criteria.json"
)


def _write_doc(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "design-doc.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_structural_probe_passes_valid_section(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path, minimal_compose_doc_markdown())
    key = first_section_key()
    result = run_structural_probe(doc_path, key, _CRITERIA)
    kinds = {item["check_id"] for item in result["items"]}
    assert "anchor_missing" not in kinds
    assert "heading_depth" not in kinds


def test_structural_probe_flags_missing_anchor(tmp_path: Path) -> None:
    key = first_section_key()
    heading = section_headings_map()[key]
    content = minimal_compose_doc_markdown().replace(
        f"## {heading} <!-- section-key:{key} -->",
        f"## {heading}",
    )
    doc_path = _write_doc(tmp_path, content)
    result = run_structural_probe(doc_path, key, _CRITERIA)
    assert any(item["check_id"] == "anchor_missing" for item in result["items"])
    anchor_item = next(item for item in result["items"] if item["check_id"] == "anchor_missing")
    assert anchor_item["fixer_action"] == "insert_anchor"


def test_structural_probe_flags_wrong_heading_depth(tmp_path: Path) -> None:
    key = first_section_key()
    heading = section_headings_map()[key]
    content = minimal_compose_doc_markdown().replace(
        f"## {heading} <!-- section-key:{key} -->",
        f"### {heading} <!-- section-key:{key} -->",
    )
    doc_path = _write_doc(tmp_path, content)
    result = run_structural_probe(doc_path, key, _CRITERIA)
    assert any(item["check_id"] == "heading_depth" for item in result["items"])


def test_mechanical_fixer_inserts_anchor_for_target_section(tmp_path: Path) -> None:
    key = first_section_key()
    other_key = [k for k in section_headings_map() if k != key][0]
    heading = section_headings_map()[key]
    content = minimal_compose_doc_markdown().replace(
        f"## {heading} <!-- section-key:{key} -->",
        f"## {heading}",
    )
    doc_path = _write_doc(tmp_path, content)
    gap_item = {
        "id": f"{key}-S-anchor_missing",
        "check_id": "anchor_missing",
        "section_key": key,
        "fixer_action": "insert_anchor",
        "skip_key": f"{key}:structural:anchor_missing",
    }
    result = apply_mechanical_fix(doc_path, gap_item)
    assert result["degraded"] is False
    updated = doc_path.read_text(encoding="utf-8")
    assert f"<!-- section-key:{key} -->" in updated
    assert f"<!-- section-key:{other_key} -->" in updated


def test_mechanical_fixer_degrades_unsupported_action(tmp_path: Path) -> None:
    key = first_section_key()
    doc_path = _write_doc(tmp_path, minimal_compose_doc_markdown())
    gap_item = {
        "id": f"{key}-S-placeholder_remaining",
        "check_id": "placeholder_remaining",
        "section_key": key,
        "fixer_action": None,
        "skip_key": f"{key}:structural:placeholder_remaining",
    }
    with pytest.raises(SystemExit) as exc:
        apply_mechanical_fix(doc_path, gap_item)
    assert exc.value.code == EXIT_DEGRADE


def test_structural_items_round_trip_schema(tmp_path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "schema" / "section" / "round"))
    from probe_report_schema import save_probe_report, validate_probe_report  # noqa: E402

    key = first_section_key()
    heading = section_headings_map()[key]
    content = minimal_compose_doc_markdown().replace(
        f"## {heading} <!-- section-key:{key} -->",
        f"## {heading}",
    )
    doc_path = _write_doc(tmp_path, content)
    probe = run_structural_probe(doc_path, key, _CRITERIA)
    item = probe["items"][0]
    report = {
        "version": "3",
        "kind": "probe",
        "round": 1,
        "revision": 1,
        "cycle_id": "test",
        "section_key": key,
        "section": heading,
        "probe_seq": 1,
        "anchor_failures": [],
        "anchor_candidates": [],
        "items": [item],
    }
    assert not validate_probe_report(report)
    out = tmp_path / "probe-001.json"
    save_probe_report(out, report)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["items"][0]["fixer_action"] == "insert_anchor"
