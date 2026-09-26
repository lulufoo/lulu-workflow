#!/usr/bin/env python3
"""Tests for compose_doc_schema.py (presentation + chapter summary, K3-d)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import SCHEMA_SECTION_DOCUMENT  # noqa: E402

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_doc_schema import (  # noqa: E402
    extract_presentation,
    get_schema,
    load_presentation_from_cycle,
    resolve_compose_doc_path_from_cycle,
)

from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402

_SCRIPT = SCHEMA_SECTION_DOCUMENT / "compose_doc_schema.py"


def _write_compose_doc(path: Path, *, title: str = "", summary: str = "Goal.") -> None:
    lines = ["---", ""]
    if title:
        lines.extend([f"# {title}", ""])
    lines.extend([
        "<!-- chapter:chap-ov -->",
        "## Overview",
        "",
        summary,
        "",
        "<!-- chapter:chap-kd -->",
        "## Key decisions",
        "",
        "KD body.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _setup_cycle(tmp_path: Path, *, active_doc: int = 1) -> tuple[Path, str]:
    from session_state_schema import save_active_doc  # noqa: WPS433
    from workflow_paths import seed_revision_profile_pointer  # noqa: WPS433

    cycle_id = "feat-session-info"
    seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
    base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "lulu-plan"
    revision = base / f"revision{active_doc}"
    revision.mkdir(parents=True)
    seed_revision_profile_pointer(revision)
    if active_doc != 1:
        save_active_doc(base / "session-state.md", active_doc)
    _write_compose_doc(
        revision / "execution" / "tech-doc.md",
        title="Feature X",
        summary="Deliver a unified session info facade.",
    )
    from workflow_state_schema import init_compose_session  # noqa: WPS433

    init_compose_session(revision / "workflow-state.md", mode="product")
    return tmp_path, cycle_id


class TestGetSchema:
    def test_presentation_fields(self):
        fields = {s["field"] for s in get_schema()}
        assert fields == {"path", "revision", "title", "summary"}


class TestExtractPresentation:
    def test_reads_h1_title_and_first_chapter_summary(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, title="Feature X", summary="Deliver unified reads.")
        payload = extract_presentation(path, revision=1)
        assert payload["title"] == "Feature X"
        assert "Deliver unified reads." in payload["summary"]
        assert payload["revision"] == 1

    def test_falls_back_to_summary_lead_when_no_h1(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_compose_doc(path, summary="Summary lead line.")
        payload = extract_presentation(path)
        # Without H1, title comes from first content in first chapter segment
        # (chapter H2 "Overview" is skipped by _first_content_line).
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

    def test_h1_only_fallback_without_chapters(self, tmp_path: Path):
        path = tmp_path / "plain.md"
        path.write_text("# Plain Title\n\nLead paragraph.\n", encoding="utf-8")
        payload = extract_presentation(path)
        assert payload["title"] == "Plain Title"
        assert "Lead paragraph." in payload["summary"]


class TestResolveFromCycle:
    def test_resolves_active_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path, active_doc=2)
        path, revision = resolve_compose_doc_path_from_cycle(cycle_id, project_root)
        assert revision == 2
        assert path.name == "tech-doc.md"
        assert path.parent.name == "execution"
        assert path.parent.parent.name == "revision2"

    def test_load_presentation_from_cycle(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = load_presentation_from_cycle(cycle_id, project_root)
        assert payload["revision"] == 1
        assert payload["title"] == "Feature X"
        assert "session info facade" in payload["summary"]


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
