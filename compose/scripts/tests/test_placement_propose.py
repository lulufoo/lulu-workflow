"""Tests for C1 propose-placement and themes coverage."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import refresh_compose_import_paths

refresh_compose_import_paths()

from placement_propose import propose_placement, themes_coverage_errors  # noqa: E402

_SECTION = Path(__file__).resolve().parents[1] / "section"
_CTL = _SECTION / "chapter_plan_control.py"


def test_propose_mechanical_and_needs_resolution() -> None:
    themes = {
        "lens_themes": [
            {
                "form_lens_id": "FL-0",
                "lens_key": "AR",
                "theme": "A",
                "desc": "d",
            },
            {
                "form_lens_id": "FL-1",
                "lens_key": "GO",
                "theme": "G",
                "desc": "d",
            },
        ]
    }
    framework = {
        "chapters": [
            {
                "id": "ch-1",
                "display_title": "One",
                "anchor_form_lens_ids": ["FL-0", "FL-1"],
                "sections": [
                    {"form_lens_id": "FL-0", "heading": "A"},
                    {"form_lens_id": "FL-1", "heading": "G"},
                ],
            }
        ]
    }
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "b", "lens_tags": ["AR", "GO"]},
        {"id": "F-3", "text": "c", "lens_tags": []},
    ]
    out = propose_placement(facts, themes, framework)
    assert out["mechanical_total"] == 1
    assert out["placement"]["chapters"][0]["facts"][0]["fid"] == "F-1"
    assert out["placement"]["chapters"][0]["facts"][0]["placement"] == "mechanical"
    assert out["needs_resolution_total"] == 1
    assert out["needs_resolution"][0]["fid"] == "F-2"
    assert out["needs_resolution"][0]["candidates"] == ["FL-0", "FL-1"]
    assert out["unmapped_total"] == 0


def test_themes_coverage_requires_present_and_required() -> None:
    themes = {
        "lens_themes": [
            {
                "form_lens_id": "FL-0",
                "lens_key": "AR",
                "theme": "A",
                "desc": "d",
            }
        ]
    }
    facts = [{"id": "F-1", "text": "a", "lens_tags": ["AR", "GO"]}]
    errors = themes_coverage_errors(
        themes,
        facts=facts,
        required_lenses=["CTX"],
        allowed_lenses=["AR", "GO", "CTX"],
    )
    assert any("GO" in e and "CTX" in e for e in errors)


def test_propose_placement_cli(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    (rev / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "a", "lens_tags": ["CTX"]}]),
        encoding="utf-8",
    )
    (rev / "_lens-themes.json").write_text(
        json.dumps(
            {
                "version": "1",
                "lens_themes": [
                    {
                        "form_lens_id": "FL-0",
                        "lens_key": "CTX",
                        "theme": "Problem theme",
                        "desc": "desc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (rev / "_chapter-framework.json").write_text(
        json.dumps(
            {
                "version": "1",
                "chapters": [
                    {
                        "id": "ch-1",
                        "display_title": "P",
                        "anchor_form_lens_ids": ["FL-0"],
                        "sections": [
                            {"form_lens_id": "FL-0", "heading": "Problem theme"}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_CTL), "propose-placement", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mechanical_total"] == 1
    assert payload["needs_resolution_total"] == 0
