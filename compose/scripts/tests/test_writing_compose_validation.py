#!/usr/bin/env python3
"""Tests for writing_compose_validation.py (narrative-arc Writing path)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_COMPOSE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_COMPOSE / "scripts" / "core"))
sys.path.insert(0, str(_COMPOSE / "scripts" / "section"))
sys.path.insert(0, str(_COMPOSE / "narrative-arc-runner" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chapter_write_state_control import main as write_state_main  # noqa: E402
from writing_compose_validation import (  # noqa: E402
    validate_display_layer_artifacts,
    validate_writing_artifacts,
)
from narrative_arc_schema import save_narrative_arc  # noqa: E402
from workflow_paths import seed_revision_profile_pointer  # noqa: E402

_PROFILE_SOURCE = (
    Path(__file__).resolve().parents[3] / "lulu-design" / "compose-profile.json"
)

_SECTION_REGISTRY = {
    "version": "1",
    "section_order": ["AR", "GO"],
    "document_preamble": "# Test\n\n",
    "sections": {
        "AR": {
            "heading": "Architecture",
            "intent": "x",
            "intent_boundary": "not y",
            "presence": "required",
        },
        "GO": {
            "heading": "Goal",
            "intent": "x",
            "intent_boundary": "not y",
            "presence": "optional",
        },
    },
}

_FORM_REGISTRY = {
    "version": "1",
    "$schema_id": "section-form-schema",
    "profile_id": "tech-design",
    "sections": {
        "AR": {
            "reading_axis": "a → b",
            "presentation": {"guidance": "p"},
            "expression": {"required": ["e"]},
        },
        "GO": {
            "reading_axis": "g → o",
            "presentation": {"guidance": "p"},
            "expression": {"required": ["e"]},
        },
    },
}


def _seed_registries(tmp_path: Path) -> tuple[Path, Path]:
    template_dir = tmp_path / "direct-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    section_path = template_dir / "section-registry.json"
    form_path = template_dir / "section-form-registry.json"
    section_path.write_text(json.dumps(_SECTION_REGISTRY), encoding="utf-8")
    form_path.write_text(json.dumps(_FORM_REGISTRY), encoding="utf-8")
    return section_path, form_path


def _write_test_profile(tmp_path: Path, section_path: Path, form_path: Path) -> Path:
    profile = json.loads(_PROFILE_SOURCE.read_text(encoding="utf-8"))
    profile["framework_templates"]["section-registry"] = section_path.as_uri()
    profile["framework_templates"]["section-form-registry"] = form_path.as_uri()
    profile_path = tmp_path / "lulu-design-compose-profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    return profile_path


def _write_facts(revision_dir: Path, facts: list[dict]) -> None:
    slice_dir = revision_dir / "L1"
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


def _slice(revision_dir: Path) -> Path:
    path = revision_dir / "L1"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _arc(*, lens: str = "AR", fact_ids: list[str] | None = None) -> dict:
    fids = fact_ids if fact_ids is not None else ["F-1"]
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": list(fids),
                "chapters": [{"lens": lens, "fact_ids": list(fids)}],
            }
        ],
    }


def _cid(lens: str = "AR") -> str:
    return f"A01-{lens}"


def _write_chapter_artifacts(
    revision_dir: Path,
    cid: str,
    *,
    body: str,
) -> None:
    (_slice(revision_dir) / f"_body-{cid}.txt").write_text(body, encoding="utf-8")


def _minimal_doc(cid: str, body: str) -> str:
    return f"# Preamble\n\n<!-- chapter:{cid} -->\n{body}\n"


def _complete_write_state(revision_dir: Path, cids: list[str]) -> None:
    project_root = revision_dir.parent
    assert write_state_main(["sync", "--revision-dir", str(revision_dir)]) == 0
    for _ in cids:
        assert write_state_main(
            [
                "begin",
                "--revision-dir",
                str(revision_dir),
                "--project-root",
                str(project_root),
            ],
        ) == 0
        assert write_state_main(
            ["complete", "--revision-dir", str(revision_dir)],
        ) == 0


def _seed_happy_path(
    revision_dir: Path,
    compose_doc: Path,
    *,
    body: str = "Architecture body with substance.",
    facts: list[dict] | None = None,
) -> list[str]:
    facts = facts or [
        {"id": "F-1", "text": "Architecture fact.", "lens_tags": ["AR"]},
    ]
    _write_facts(revision_dir, facts)
    save_narrative_arc(_slice(revision_dir) / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body=body)
    compose_doc.write_text(_minimal_doc(cid, body), encoding="utf-8")
    _complete_write_state(revision_dir, [cid])
    return [cid]


@pytest.fixture
def revision_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    section_path, form_path = _seed_registries(tmp_path)
    profile_path = _write_test_profile(tmp_path, section_path, form_path)
    import workflow_paths

    monkeypatch.setattr(
        workflow_paths,
        "compose_profile_path",
        lambda _profile_id: profile_path,
    )
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev, profile_id="lulu-design")
    return rev


def test_passes_with_minimal_narrative_arc(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_dispatch_via_validate_writing_artifacts(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    error = validate_writing_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_requires_narrative_arc(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    compose_doc.write_text("# Doc\n", encoding="utf-8")
    _write_facts(
        revision_dir,
        [{"id": "F-1", "text": "Architecture fact.", "lens_tags": ["AR"]}],
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "missing _narrative-arc.json" in error


def test_fails_when_facts_missing(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    compose_doc.write_text("# Doc\n", encoding="utf-8")
    save_narrative_arc(_slice(revision_dir) / "_narrative-arc.json", _arc())
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "invalid or missing _facts.json" in error


def test_fails_when_facts_json_invalid(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (_slice(revision_dir) / "_facts.json").write_text("not json", encoding="utf-8")
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "invalid or missing _facts.json" in error


@pytest.mark.parametrize(
    "retired_name",
    [
        "_chapters.json",
        "_lens-themes.json",
        "_chapter-framework.json",
        "_chapter-placement.json",
    ],
)
def test_fails_when_retired_plan_file_present(
    revision_dir: Path, tmp_path: Path, retired_name: str,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (_slice(revision_dir) / retired_name).write_text("{}", encoding="utf-8")
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "retired:" in error
    assert retired_name in error


def test_fails_when_write_state_incomplete(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _write_facts(
        revision_dir,
        [{"id": "F-1", "text": "Architecture fact.", "lens_tags": ["AR"]}],
    )
    save_narrative_arc(_slice(revision_dir) / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body="body")
    compose_doc.write_text(_minimal_doc(cid, "body"), encoding="utf-8")
    # sync only — not complete
    assert write_state_main(["sync", "--revision-dir", str(revision_dir)]) == 0
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "4.W:" in error


def test_fails_when_chapter_body_file_whitespace_only(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (_slice(revision_dir) / f"_body-{_cid()}.txt").write_text("   \n\n", encoding="utf-8")
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert f"empty body file _body-{_cid()}.txt" in error


def test_fails_when_chapter_body_missing(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (_slice(revision_dir) / f"_body-{_cid()}.txt").unlink()
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert f"missing _body-{_cid()}.txt" in error


def test_allows_missing_derive(revision_dir: Path, tmp_path: Path):
    """_derive is not a Writing hard gate (archive-7.0)."""
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    derive = _slice(revision_dir) / f"_derive-{_cid()}.json"
    if derive.is_file():
        derive.unlink()
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_fails_when_chapter_anchor_missing_in_doc(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    compose_doc.write_text("# Preamble\n\nNo chapter anchor here.\n", encoding="utf-8")
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "missing chapter anchor in compose document" in error


def test_fails_when_doc_chapter_body_empty(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    compose_doc.write_text(
        f"# Preamble\n\n<!-- chapter:{_cid()} -->\n",
        encoding="utf-8",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "compose document empty chapter body" in error


def test_fails_when_doc_chapter_body_is_title_only(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    compose_doc.write_text(
        f"# Preamble\n\n<!-- chapter:{_cid()} -->\n## 架构\n\n",
        encoding="utf-8",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "compose document empty chapter body" in error


def test_does_not_strip_h3_only_first_line_as_title(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    compose_doc.write_text(
        f"# Preamble\n\n<!-- chapter:{_cid()} -->\n### Only text, no H2 title\n",
        encoding="utf-8",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def _seed_discovered_anchor_case(
    revision_dir: Path,
    compose_doc: Path,
    *,
    anchors: list[dict],
    body: str,
) -> None:
    facts = [
        {
            "id": "F-1",
            "text": "Attachment copies live under the task dir.",
            "lens_tags": ["AR"],
            "origin": {"type": "discovered", "ref": ["O-1"]},
            "anchors": anchors,
        },
    ]
    _write_facts(revision_dir, facts)
    save_narrative_arc(_slice(revision_dir) / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body=body)
    compose_doc.write_text(_minimal_doc(cid, body), encoding="utf-8")
    _complete_write_state(revision_dir, [cid])


def test_l6_fails_when_discovered_anchor_absent_from_body(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        revision_dir,
        compose_doc,
        anchors=[{"kind": "path", "value": "tasks/{id}/attachments/"}],
        body="The attachment copies are stored somewhere sensible.",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "L6:" in error
    assert "F-1 anchor" in error
    assert "missing from body" in error


def test_l6_passes_when_discovered_anchor_present_in_body(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        revision_dir,
        compose_doc,
        anchors=[{"kind": "path", "value": "tasks/{id}/attachments/"}],
        body="Copies land in `tasks/{id}/attachments/` next to the task.",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_l6_code_ref_matches_symbol_segment_only(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        revision_dir,
        compose_doc,
        anchors=[{"kind": "code_ref", "value": "paths.rs::plan_tasks_task_dir"}],
        body="The `plan_tasks_task_dir` helper resolves the directory.",
    )
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_l6_ignores_seed_facts_under_s1(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    facts = [
        {
            "id": "F-1",
            "text": "Seed architecture decision.",
            "lens_tags": ["AR"],
            "origin": {"type": "seed", "ref": ["scope"]},
            "anchors": [{"kind": "path", "value": "never/in/body/"}],
        },
    ]
    _write_facts(revision_dir, facts)
    save_narrative_arc(_slice(revision_dir) / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body="Chapter body.")
    compose_doc.write_text(_minimal_doc(cid, "Chapter body."), encoding="utf-8")
    _complete_write_state(revision_dir, [cid])
    error = validate_display_layer_artifacts(
        _slice(revision_dir), compose_doc, tmp_path, "lulu-design",
    )
    assert error is None
