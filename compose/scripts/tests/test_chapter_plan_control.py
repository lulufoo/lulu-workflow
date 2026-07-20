"""Tests for archive-3.0 chapter_plan_control (themes → framework → placement)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parents[1] / "section"
_CTL = _SECTION / "chapter_plan_control.py"


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CTL), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_plan_files(tmp_path: Path, rev: Path) -> None:
    themes = {
        "version": "1",
        "lens_themes": [
            {
                "form_lens_id": "FL-0",
                "lens_key": "CTX",
                "theme": "Problem theme",
                "desc": "Problem clustering desc.",
            },
            {
                "form_lens_id": "FL-1",
                "lens_key": "GO",
                "theme": "Success theme",
                "desc": "Success clustering desc.",
            },
        ],
    }
    themes_file = tmp_path / "themes.json"
    themes_file.write_text(json.dumps(themes), encoding="utf-8")
    r1 = _run(
        [
            "write-themes",
            "--revision-dir",
            str(rev),
            "--themes-file",
            str(themes_file),
        ]
    )
    assert r1.returncode == 0, r1.stderr

    framework = {
        "version": "1",
        "chapters": [
            {
                "id": "ch-1",
                "display_title": "Problem and success",
                "anchor_form_lens_ids": ["FL-0", "FL-1"],
                "sections": [
                    {"form_lens_id": "FL-0", "heading": "Problem theme"},
                    {"form_lens_id": "FL-1", "heading": "Success theme"},
                ],
            }
        ],
    }
    fw_file = tmp_path / "framework.json"
    fw_file.write_text(json.dumps(framework), encoding="utf-8")
    r2 = _run(
        [
            "write-framework",
            "--revision-dir",
            str(rev),
            "--framework-file",
            str(fw_file),
        ]
    )
    assert r2.returncode == 0, r2.stderr

    placement = {
        "version": "1",
        "$schema_id": "chapter-placement",
        "chapters": [
            {
                "id": "ch-1",
                "facts": [
                    {
                        "fid": "F-1",
                        "form_lens_id": "FL-0",
                        "placement": "mechanical",
                    },
                    {
                        "fid": "F-2",
                        "form_lens_id": "FL-1",
                        "placement": "mechanical",
                    },
                ],
            }
        ],
    }
    pl_file = tmp_path / "placement.json"
    pl_file.write_text(json.dumps(placement), encoding="utf-8")
    r3 = _run(
        [
            "write-placement",
            "--revision-dir",
            str(rev),
            "--placement-file",
            str(pl_file),
        ]
    )
    assert r3.returncode == 0, r3.stderr


def test_write_plan_validate_and_list_chapters(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    _seed_plan_files(tmp_path, rev)

    assert not (rev / "_chapters.json").exists()
    placement_disk = json.loads((rev / "_chapter-placement.json").read_text(encoding="utf-8"))
    assert placement_disk["chapters"][0]["id"] == "ch-1"
    assert {f["fid"] for f in placement_disk["chapters"][0]["facts"]} == {"F-1", "F-2"}

    r4 = _run(["validate", "--revision-dir", str(rev)])
    assert r4.returncode == 0, r4.stderr

    r5 = _run(["list-chapters", "--revision-dir", str(rev)])
    assert r5.returncode == 0, r5.stderr
    payload = json.loads(r5.stdout)
    assert payload["chapter_ids"] == ["ch-1"]


def test_write_framework_rejects_heading_theme_mismatch(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    themes = {
        "version": "1",
        "lens_themes": [
            {
                "form_lens_id": "FL-0",
                "lens_key": "CTX",
                "theme": "Problem theme",
                "desc": "Problem clustering desc.",
            }
        ],
    }
    themes_file = tmp_path / "themes.json"
    themes_file.write_text(json.dumps(themes), encoding="utf-8")
    assert (
        _run(
            [
                "write-themes",
                "--revision-dir",
                str(rev),
                "--themes-file",
                str(themes_file),
            ]
        ).returncode
        == 0
    )

    framework = {
        "version": "1",
        "chapters": [
            {
                "id": "ch-1",
                "display_title": "Problem",
                "anchor_form_lens_ids": ["FL-0"],
                "sections": [{"form_lens_id": "FL-0", "heading": "Wrong heading"}],
            }
        ],
    }
    fw_file = tmp_path / "framework.json"
    fw_file.write_text(json.dumps(framework), encoding="utf-8")
    r = _run(
        [
            "write-framework",
            "--revision-dir",
            str(rev),
            "--framework-file",
            str(fw_file),
        ]
    )
    assert r.returncode != 0
    assert "heading" in r.stderr.lower() or "theme" in r.stderr.lower()


def test_render_chapter_ids_skips_empty_placement_chapter() -> None:
    sys.path.insert(0, str(_SECTION))
    from chapter_plan_control import _render_chapter_ids  # noqa: E402

    framework = {
        "chapters": [
            {"id": "ch-1"},
            {"id": "ch-empty"},
            {"id": "ch-orphan"},
        ]
    }
    placement = {
        "chapters": [
            {"id": "ch-1", "facts": [{"fid": "F-1", "form_lens_id": "FL-0"}]},
            {"id": "ch-empty", "facts": []},
        ]
    }
    assert _render_chapter_ids(framework, placement) == ["ch-1"]


def test_rejects_retired_chapters_json(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    _seed_plan_files(tmp_path, rev)
    (rev / "_chapters.json").write_text("[]", encoding="utf-8")

    r = _run(["validate", "--revision-dir", str(rev)])
    assert r.returncode != 0
    assert "retired _chapters.json" in r.stderr

    r2 = _run(["list-chapters", "--revision-dir", str(rev)])
    assert r2.returncode != 0
    assert "retired _chapters.json" in r2.stderr
