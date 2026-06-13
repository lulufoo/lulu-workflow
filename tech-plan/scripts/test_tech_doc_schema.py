#!/usr/bin/env python3
"""Tests for tech-plan tech_doc_schema.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tech_doc_schema import (  # noqa: E402
    extract_presentation,
    get_schema,
    load_presentation_from_cycle,
    resolve_tech_doc_path_from_cycle,
)

_SCRIPT = Path(__file__).resolve().parent / "tech_doc_schema.py"


def _write_tech_doc(path: Path, *, title: str = "", north_star: str = "Goal.") -> None:
    lines = ["---", ""]
    if title:
        lines.extend([f"# {title}", ""])
    lines.extend([
        "## North Star",
        "",
        north_star,
        "",
        "## Key Decisions",
        "",
        "KD.",
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
    _write_tech_doc(
        revision / "tech-doc.md",
        title="Feature X",
        north_star="Deliver a unified session info facade.",
    )
    from workflow_state_schema import init_drafting  # noqa: WPS433

    init_drafting(
        revision / "workflow-state.md",
        mode="product",
        product_ref="/p.md",
    )
    return tmp_path, cycle_id


class TestGetSchema:
    def test_presentation_fields(self):
        fields = {s["field"] for s in get_schema()}
        assert fields == {"path", "revision", "title", "summary"}


class TestExtractPresentation:
    def test_reads_h1_title_and_north_star_summary(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_tech_doc(path, title="Feature X", north_star="Deliver unified reads.")
        payload = extract_presentation(path, revision=1)
        assert payload["title"] == "Feature X"
        assert payload["summary"] == "Deliver unified reads."
        assert payload["revision"] == 1

    def test_falls_back_to_north_star_lead_when_no_h1(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_tech_doc(path, north_star="North star lead line.")
        payload = extract_presentation(path)
        assert payload["title"] == "North star lead line."

    def test_truncates_long_summary(self, tmp_path: Path):
        path = tmp_path / "tech-doc.md"
        _write_tech_doc(path, north_star="x" * 400)
        payload = extract_presentation(path)
        assert len(payload["summary"]) == 300
        assert payload["summary"].endswith("…")

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            extract_presentation(tmp_path / "missing.md")


class TestResolveFromCycle:
    def test_resolves_active_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path, active_doc=2)
        path, revision = resolve_tech_doc_path_from_cycle(cycle_id, project_root)
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
        _write_tech_doc(path, title="CLI Title", north_star="CLI summary.")
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--read", "--path", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["title"] == "CLI Title"
