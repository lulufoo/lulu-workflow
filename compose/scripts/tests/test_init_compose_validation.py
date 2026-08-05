#!/usr/bin/env python3
"""Tests for init_compose_validation.py (narrative-arc Init path)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chapter_write_state_control import main as write_state_main  # noqa: E402
from init_compose_validation import (  # noqa: E402
    validate_display_layer_artifacts,
    validate_init_artifacts,
)
from narrative_arc_schema import save_narrative_arc  # noqa: E402
from test_template_data import seed_template_cache  # noqa: E402

_FAKE_DESIGN_SECTION_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/design/42-tech-design-section-registry.json"
)

_SECTION_REGISTRY = {
    "version": "1",
    "section_order": ["AR", "GO"],
    "document_preamble": "# Test\n\n",
    "sections": {
        "AR": {"heading": "Architecture", "intent": "x", "presence": "required"},
        "GO": {"heading": "Goal", "intent": "x", "presence": "optional"},
    },
}


def _ensure_stage_compose(tmp_path: Path, stage: str, compose: dict) -> None:
    root = tmp_path / "skill-config" / "lulu-dev-workflow"
    stages = root / "stages"
    stages.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps({"version": 1, "layout": "stages"}) + "\n",
            encoding="utf-8",
        )
    path = stages / f"{stage}.json"
    payload: dict = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    nested = dict(payload.get("compose") or {})
    nested.update(compose)
    payload["compose"] = nested
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_registries(tmp_path: Path) -> None:
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_section_registry_url",
        _SECTION_REGISTRY,
    )
    _ensure_stage_compose(
        tmp_path,
        "lulu-design",
        {"tdt_section_registry_url": _FAKE_DESIGN_SECTION_URL},
    )


def _write_facts(revision_dir: Path, facts: list[dict]) -> None:
    (revision_dir / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


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
    (revision_dir / f"_body-{cid}.txt").write_text(body, encoding="utf-8")


def _minimal_doc(cid: str, body: str) -> str:
    return f"# Preamble\n\n<!-- chapter:{cid} -->\n{body}\n"


def _complete_write_state(revision_dir: Path, cids: list[str]) -> None:
    assert write_state_main(["sync", "--revision-dir", str(revision_dir)]) == 0
    for _ in cids:
        assert write_state_main(
            ["begin", "--revision-dir", str(revision_dir)],
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
    save_narrative_arc(revision_dir / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body=body)
    compose_doc.write_text(_minimal_doc(cid, body), encoding="utf-8")
    _complete_write_state(revision_dir, [cid])
    return [cid]


@pytest.fixture
def revision_dir(tmp_path: Path) -> Path:
    _seed_registries(tmp_path)
    rev = tmp_path / "revision1"
    rev.mkdir()
    return rev


def test_passes_with_minimal_narrative_arc(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_dispatch_via_validate_init_artifacts(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    error = validate_init_artifacts(
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "missing _narrative-arc.json" in error


def test_fails_when_facts_missing(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    compose_doc.write_text("# Doc\n", encoding="utf-8")
    save_narrative_arc(revision_dir / "_narrative-arc.json", _arc())
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "invalid or missing _facts.json" in error


def test_fails_when_facts_json_invalid(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (revision_dir / "_facts.json").write_text("not json", encoding="utf-8")
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
    (revision_dir / retired_name).write_text("{}", encoding="utf-8")
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
    save_narrative_arc(revision_dir / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body="body")
    compose_doc.write_text(_minimal_doc(cid, "body"), encoding="utf-8")
    # sync only — not complete
    assert write_state_main(["sync", "--revision-dir", str(revision_dir)]) == 0
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert "4.W:" in error


def test_fails_when_chapter_body_file_whitespace_only(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (revision_dir / f"_body-{_cid()}.txt").write_text("   \n\n", encoding="utf-8")
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert f"empty body file _body-{_cid()}.txt" in error


def test_fails_when_chapter_body_missing(revision_dir: Path, tmp_path: Path):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    (revision_dir / f"_body-{_cid()}.txt").unlink()
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is not None
    assert f"missing _body-{_cid()}.txt" in error


def test_allows_missing_derive(revision_dir: Path, tmp_path: Path):
    """_derive is not an Init hard gate (archive-7.0)."""
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    derive = revision_dir / f"_derive-{_cid()}.json"
    if derive.is_file():
        derive.unlink()
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is None


def test_fails_when_chapter_anchor_missing_in_doc(
    revision_dir: Path, tmp_path: Path,
):
    compose_doc = revision_dir / "design-doc.md"
    _seed_happy_path(revision_dir, compose_doc)
    compose_doc.write_text("# Preamble\n\nNo chapter anchor here.\n", encoding="utf-8")
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
    save_narrative_arc(revision_dir / "_narrative-arc.json", _arc())
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
        revision_dir, compose_doc, tmp_path, "lulu-design",
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
    save_narrative_arc(revision_dir / "_narrative-arc.json", _arc())
    cid = _cid()
    _write_chapter_artifacts(revision_dir, cid, body="Chapter body.")
    compose_doc.write_text(_minimal_doc(cid, "Chapter body."), encoding="utf-8")
    _complete_write_state(revision_dir, [cid])
    error = validate_display_layer_artifacts(
        revision_dir, compose_doc, tmp_path, "lulu-design",
    )
    assert error is None
