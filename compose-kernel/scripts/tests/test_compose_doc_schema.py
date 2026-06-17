#!/usr/bin/env python3
"""Tests for tech-plan compose_doc_schema.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_registry_schema import section_heading, summary_section_key  # noqa: E402
from compose_doc_schema import format_section_heading  # noqa: E402
from test_registry_fixtures import fourth_section_key  # noqa: E402
from compose_doc_schema import (  # noqa: E402
    extract_presentation,
    get_schema,
    load_presentation_from_cycle,
    resolve_compose_doc_path_from_cycle,
)

import bootstrap  # noqa: F401
from bootstrap import SCHEMA_SECTION_DOCUMENT, SECTION  # noqa: E402
from init_drafting_helpers import product_delivered_refs  # noqa: E402

_SCRIPT = SCHEMA_SECTION_DOCUMENT / "compose_doc_schema.py"


def _write_compose_doc(path: Path, *, title: str = "", summary: str = "Goal.") -> None:
    summary_key = summary_section_key()
    kd_key = fourth_section_key()
    lines = ["---", ""]
    if title:
        lines.extend([f"# {title}", ""])
    lines.extend([
        format_section_heading(summary_key, section_heading(summary_key)),
        "",
        summary,
        "",
        format_section_heading(kd_key, section_heading(kd_key)),
        "",
        f"{kd_key}.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _setup_cycle(tmp_path: Path, *, active_doc: int = 1) -> tuple[Path, str]:
    cycle_id = "feat-session-info"
    base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\n---\n",
        encoding="utf-8",
    )
    revision = base / f"revision{active_doc}"
    revision.mkdir(parents=True)
    _write_compose_doc(
        revision / "tech-doc.md",
        title="Feature X",
        summary="Deliver a unified session info facade.",
    )
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433
    from workflow_state_schema import init_drafting  # noqa: WPS433

    init_drafting(
        revision / "workflow-state.md",
        mode="product",
        delivered_refs=product_delivered_refs("/p.md"),
    )
    return tmp_path, cycle_id


class TestGetSchema:
    def test_presentation_fields(self):
        fields = {s["field"] for s in get_schema()}
        assert fields == {"path", "revision", "title", "summary"}


class TestExtractPresentation:
    def test_reads_h1_title_and_summary_section(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, title="Feature X", summary="Deliver unified reads.")
        payload = extract_presentation(path, revision=1)
        assert payload["title"] == "Feature X"
        assert payload["summary"] == "Deliver unified reads."
        assert payload["revision"] == 1

    def test_falls_back_to_summary_lead_when_no_h1(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, summary="Summary lead line.")
        payload = extract_presentation(path)
        assert payload["title"] == "Summary lead line."

    def test_truncates_long_summary(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, summary="x" * 400)
        payload = extract_presentation(path)
        assert len(payload["summary"]) == 300
        assert payload["summary"].endswith("…")

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            extract_presentation(tmp_path / "missing.md")


class TestSectionKeyAnchors:
    def test_section_body_by_key_uses_anchor(self, tmp_path: Path):
        from compose_doc_schema import section_body_by_key, section_display_heading

        path = tmp_path / "tech-doc.md"
        key = summary_section_key()
        path.write_text(
            f"---\n\n{format_section_heading(key, 'Custom title')}\n\nAnchor body.\n",
            encoding="utf-8",
        )
        raw = path.read_text(encoding="utf-8")
        assert section_body_by_key(raw, key) == "Anchor body."
        assert section_display_heading(raw, key) == "Custom title"

    def test_legacy_heading_fallback(self, tmp_path: Path):
        from compose_doc_schema import section_body_by_key

        key = summary_section_key()
        heading = section_heading(key)
        path = tmp_path / "legacy.md"
        path.write_text(f"---\n\n## {heading}\n\nLegacy body.\n", encoding="utf-8")
        raw = path.read_text(encoding="utf-8")
        assert section_body_by_key(raw, key) == "Legacy body."

    def test_outline_block_intent_anchors(self, tmp_path: Path):
        from compose_doc_schema import parse_sections, section_body_by_key

        doc = """---
---

## Overview

<!-- section-key:CTX -->
Context body.

<!-- section-key:GO -->
Goal body.

## Boundaries

<!-- section-key:NG -->
Non-goals body.
"""
        raw = doc
        parsed = parse_sections(raw)
        assert set(parsed) >= {"CTX", "GO", "NG"}
        assert section_body_by_key(raw, "CTX") == "Context body."
        assert section_body_by_key(raw, "GO") == "Goal body."
        assert section_body_by_key(raw, "NG") == "Non-goals body."
        assert parsed["CTX"]["display_heading"] == ""
        assert parsed["NG"]["display_heading"] == ""


class TestResolveFromCycle:
    def test_resolves_active_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path, active_doc=2)
        path, revision = resolve_compose_doc_path_from_cycle(cycle_id, project_root)
        assert revision == 2
        assert path.name == "tech-doc.md"
        assert path.parent.name == "revision2"

    def test_load_presentation_from_cycle(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = load_presentation_from_cycle(cycle_id, project_root)
        assert payload["revision"] == 1
        assert payload["title"] == "Feature X"
        assert payload["summary"] == "Deliver a unified session info facade."


class TestCli:
    def test_schema_flag(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--schema"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)

    def test_read_by_path(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, title="CLI Title", summary="CLI summary.")
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--read", "--path", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["title"] == "CLI Title"
