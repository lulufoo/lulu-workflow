#!/usr/bin/env python3
"""Tests for init_compose_validation.py (display-layer only, K3-d)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from init_compose_validation import (  # noqa: E402
    validate_display_layer_artifacts,
    validate_init_artifacts,
)
from test_template_data import seed_template_cache  # noqa: E402

_FAKE_DESIGN_SECTION_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/design/42-tech-design-section-registry.json"
)
_FAKE_DESIGN_OUTLINE_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/design/45-tech-design-feature-outline-registry.json"
)


def _ensure_stage_compose(tmp_path: Path, stage: str, compose: dict) -> None:
    """Write stages/{stage}.json compose URLs under tmp_path skill-config."""
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

# --- display_layer branch (fact-first display layer, M4a) ---

_DISPLAY_LAYER_SECTION_REGISTRY = {
    "version": "1",
    "section_order": ["AR", "GO"],
    "document_preamble": "# Test\n\n",
    "sections": {
        "AR": {"heading": "Architecture", "intent": "x", "presence": "required"},
        "GO": {"heading": "Goal", "intent": "x", "presence": "optional"},
    },
}

_DISPLAY_LAYER_OUTLINE_CANDIDATES = {
    "version": "1",
    "$schema_id": "outline-schema",
    "candidates": [
        {"block": "cand-1", "anchor_lenses": ["AR"]},
        {"block": "cand-2", "anchor_lenses": ["GO"]},
    ],
}

_DISPLAY_LAYER_OUTLINE_LEGACY = {
    "version": "1",
    "$schema_id": "outline-schema",
    "outline_order": ["OV"],
    "blocks": {"OV": {"heading": "Overview", "intents": ["AR", "GO"]}},
}


def _seed_display_layer_registries(tmp_path: Path, *, outline: dict | None = None) -> None:
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_section_registry_url",
        _DISPLAY_LAYER_SECTION_REGISTRY,
    )
    seed_template_cache(
        tmp_path,
        "lulu-design",
        "tdt_outline_registry_url",
        outline if outline is not None else _DISPLAY_LAYER_OUTLINE_CANDIDATES,
    )
    _ensure_stage_compose(
        tmp_path,
        "lulu-design",
        {
            "tdt_section_registry_url": _FAKE_DESIGN_SECTION_URL,
            "tdt_outline_registry_url": _FAKE_DESIGN_OUTLINE_URL,
        },
    )


def _write_facts(revision_dir: Path, facts: list[dict]) -> None:
    (revision_dir / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_chapters(revision_dir: Path, chapters: list[dict]) -> None:
    (revision_dir / "_chapters.json").write_text(
        json.dumps(chapters, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_chapter_artifacts(revision_dir: Path, cid: str, *, title: str, body: str) -> None:
    (revision_dir / f"_derive-{cid}.json").write_text(
        json.dumps({"display_title": title}, ensure_ascii=False),
        encoding="utf-8",
    )
    (revision_dir / f"_body-{cid}.txt").write_text(body, encoding="utf-8")


def _minimal_display_layer_doc(cid: str, title: str, body: str) -> str:
    return f"# Preamble\n\n<!-- chapter:{cid} -->\n## {title}\n\n{body}\n"


@pytest.fixture
def display_layer_revision_dir(tmp_path: Path) -> Path:
    _seed_display_layer_registries(tmp_path)
    path = tmp_path / "revision1"
    path.mkdir()
    return path


def _seed_happy_path(revision_dir: Path, compose_doc: Path) -> None:
    _write_facts(
        revision_dir,
        [{"id": "F-1", "text": "Architecture fact.", "lens_tags": ["AR"]}],
    )
    _write_chapters(
        revision_dir,
        [
            {
                "id": "chap-1",
                "anchor_lenses": ["AR"],
                "derived_from": ["cand-1"],
                "op": "keep",
                "facts": [{"fid": "F-1", "form_lens": "AR"}],
            },
        ],
    )
    _write_chapter_artifacts(revision_dir, "chap-1", title="架构", body="Chapter body.")
    compose_doc.write_text(
        _minimal_display_layer_doc("chap-1", "架构", "Chapter body."),
        encoding="utf-8",
    )


def test_display_layer_passes_with_minimal_artifacts(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_display_layer_dispatch_via_validate_init_artifacts(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """validate_init_artifacts always runs the display-layer suite (K3-d)."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)

    error = validate_init_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_display_layer_requires_candidates_shaped_outline(
    display_layer_revision_dir: Path, tmp_path: Path
):
    _seed_display_layer_registries(tmp_path, outline=_DISPLAY_LAYER_OUTLINE_LEGACY)
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "candidates-shaped outline-registry" in error


def test_display_layer_fails_when_facts_missing(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_facts.json").unlink()

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "missing _facts.json" in error


def test_display_layer_fails_when_chapters_missing(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_chapters.json").unlink()

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "missing _chapters.json" in error


def test_display_layer_fails_when_facts_json_invalid(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """m4 (round-1 review test-gap): malformed _facts.json must be reported,
    not raise past validate_display_layer_artifacts."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_facts.json").write_text("not json", encoding="utf-8")

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "invalid or missing _facts.json" in error


def test_display_layer_fails_when_chapters_json_invalid(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """m4 (round-1 review test-gap): malformed _chapters.json must be
    reported, not raise past validate_display_layer_artifacts."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_chapters.json").write_text("not json", encoding="utf-8")

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "invalid or missing _chapters.json" in error


def test_display_layer_fails_when_chapter_body_file_whitespace_only(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """m4 (round-1 review test-gap): a _body-{cid}.txt containing only
    whitespace must be treated as an empty body artifact, same as a
    zero-byte file."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_body-chap-1.txt").write_text("   \n\n", encoding="utf-8")

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "empty body file _body-chap-1.txt" in error


def test_display_layer_fails_on_c1_coverage_gap(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """Regression guard for §11.4 Blocker#1: section_order/presence_map must
    actually reach run_display_layer_gates, or this required-lens gap would
    silently no-op."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _write_facts(
        display_layer_revision_dir,
        [{"id": "F-1", "text": "Goal fact.", "lens_tags": ["GO"]}],
    )
    _write_chapters(
        display_layer_revision_dir,
        [
            {
                "id": "chap-1",
                "anchor_lenses": ["GO"],
                "derived_from": ["cand-2"],
                "op": "keep",
                "facts": [{"fid": "F-1", "form_lens": "GO"}],
            },
        ],
    )
    _write_chapter_artifacts(display_layer_revision_dir, "chap-1", title="目标", body="Goal body.")
    compose_doc.write_text(
        _minimal_display_layer_doc("chap-1", "目标", "Goal body."),
        encoding="utf-8",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "C1: required lens 'AR'" in error


def test_display_layer_fails_when_chapter_body_missing(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_body-chap-1.txt").unlink()

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "missing _body-chap-1.txt" in error


def test_display_layer_fails_when_chapter_derive_missing_title(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    (display_layer_revision_dir / "_derive-chap-1.json").write_text(
        json.dumps({"display_title": ""}), encoding="utf-8",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "display_title missing" in error


def test_display_layer_fails_when_chapter_anchor_missing_in_doc(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    compose_doc.write_text("# Preamble\n\nNo chapter anchor here.\n", encoding="utf-8")

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "missing chapter anchor in compose document" in error


def test_display_layer_fails_when_doc_chapter_body_empty(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    compose_doc.write_text("# Preamble\n\n<!-- chapter:chap-1 -->\n", encoding="utf-8")

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "compose document empty chapter body" in error


def test_display_layer_fails_when_doc_chapter_body_is_title_only(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """Round-1 Grok review m1: a chapter segment containing only the rendered
    "## {title}" heading (no prose) must not pass as non-empty content — the
    check must strip the heading line before the emptiness test."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    compose_doc.write_text(
        "# Preamble\n\n<!-- chapter:chap-1 -->\n## 架构\n\n",
        encoding="utf-8",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "compose document empty chapter body" in error


def test_display_layer_does_not_strip_h3_only_first_line_as_title(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """Round-2 Grok review N1: the title-strip must match exactly "## " (and
    reject "### "), or a malformed segment whose only line is an H3 would be
    mistaken for the rendered H2 title and stripped away, producing a false
    "empty chapter body" error even though the line is real content."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)
    compose_doc.write_text(
        "# Preamble\n\n<!-- chapter:chap-1 -->\n### Only text, no H2 title\n",
        encoding="utf-8",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_display_layer_fails_when_outline_fetch_returns_none(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """Round-1 Grok review m2: an outline-registry fetch/parse failure
    (``outline_registry_for_profile`` returns ``None``) must be reported
    distinctly from a legacy-shaped (missing candidates) registry."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)

    with mock.patch(
        "init_compose_validation.outline_registry_for_profile",
        return_value=None,
    ):
        error = validate_display_layer_artifacts(
            display_layer_revision_dir,
            compose_doc,
            tmp_path,
            "lulu-design",
        )
    assert error is not None
    assert "fetch/parse" in error
    assert "candidates-shaped" not in error


def test_display_layer_fails_when_outline_candidates_empty(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """Round-1 Grok review m3: an empty/null candidates list must be
    rejected by the pairing check itself, not silently pass through to L5
    (which would then fail every chapter with a confusing message)."""
    _seed_display_layer_registries(
        tmp_path,
        outline={"version": "1", "$schema_id": "outline-schema", "candidates": []},
    )
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_happy_path(display_layer_revision_dir, compose_doc)

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "candidates-shaped outline-registry" in error


def _seed_discovered_anchor_case(
    revision_dir: Path,
    compose_doc: Path,
    *,
    anchors: list[dict],
    body: str,
) -> None:
    """Seed one discovered AR fact carrying ``anchors`` with a given chapter body."""
    _write_facts(
        revision_dir,
        [
            {
                "id": "F-1",
                "text": "Attachment copies live under the task dir.",
                "lens_tags": ["AR"],
                "origin": {"type": "discovered", "ref": ["O-1"]},
                "anchors": anchors,
            },
        ],
    )
    _write_chapters(
        revision_dir,
        [
            {
                "id": "chap-1",
                "anchor_lenses": ["AR"],
                "derived_from": ["cand-1"],
                "op": "keep",
                "facts": [{"fid": "F-1", "form_lens": "AR"}],
            },
        ],
    )
    _write_chapter_artifacts(revision_dir, "chap-1", title="架构", body=body)
    compose_doc.write_text(
        _minimal_display_layer_doc("chap-1", "架构", body),
        encoding="utf-8",
    )


def test_l6_fails_when_discovered_anchor_absent_from_body(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        display_layer_revision_dir,
        compose_doc,
        anchors=[{"kind": "path", "value": "tasks/{id}/attachments/"}],
        body="The attachment copies are stored somewhere sensible.",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is not None
    assert "F-1 anchor" in error
    assert "missing from body" in error


def test_l6_passes_when_discovered_anchor_present_in_body(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        display_layer_revision_dir,
        compose_doc,
        anchors=[{"kind": "path", "value": "tasks/{id}/attachments/"}],
        body="Copies land in `tasks/{id}/attachments/` next to the task.",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_l6_code_ref_matches_symbol_segment_only(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """code_ref coverage is OR over path/symbol segments: the symbol appearing
    in body (without the path) must pass."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _seed_discovered_anchor_case(
        display_layer_revision_dir,
        compose_doc,
        anchors=[{"kind": "code_ref", "value": "paths.rs::plan_tasks_task_dir"}],
        body="The `plan_tasks_task_dir` helper resolves the directory.",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_l6_ignores_seed_facts_under_s1(
    display_layer_revision_dir: Path, tmp_path: Path
):
    """S1 strictness: only origin.type=discovered facts are enforced; a seed
    fact whose anchor is absent from body must not fail L6."""
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _write_facts(
        display_layer_revision_dir,
        [
            {
                "id": "F-1",
                "text": "Seed architecture decision.",
                "lens_tags": ["AR"],
                "origin": {"type": "seed", "ref": ["scope"]},
                "anchors": [{"kind": "path", "value": "never/in/body/"}],
            },
        ],
    )
    _write_chapters(
        display_layer_revision_dir,
        [
            {
                "id": "chap-1",
                "anchor_lenses": ["AR"],
                "derived_from": ["cand-1"],
                "op": "keep",
                "facts": [{"fid": "F-1", "form_lens": "AR"}],
            },
        ],
    )
    _write_chapter_artifacts(
        display_layer_revision_dir, "chap-1", title="架构", body="Chapter body."
    )
    compose_doc.write_text(
        _minimal_display_layer_doc("chap-1", "架构", "Chapter body."),
        encoding="utf-8",
    )

    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None


def test_display_layer_skips_artifact_checks_for_drop_chapters(
    display_layer_revision_dir: Path, tmp_path: Path
):
    compose_doc = display_layer_revision_dir / "design-doc.md"
    _write_facts(
        display_layer_revision_dir,
        [{"id": "F-1", "text": "Architecture fact.", "lens_tags": ["AR"]}],
    )
    _write_chapters(
        display_layer_revision_dir,
        [
            {
                "id": "chap-1",
                "anchor_lenses": ["AR"],
                "derived_from": ["cand-1"],
                "op": "keep",
                "facts": [{"fid": "F-1", "form_lens": "AR"}],
            },
            {
                "id": "chap-2",
                "anchor_lenses": ["GO"],
                "derived_from": ["cand-2"],
                "op": "drop",
                "facts": [],
            },
        ],
    )
    _write_chapter_artifacts(display_layer_revision_dir, "chap-1", title="架构", body="Chapter body.")
    compose_doc.write_text(
        _minimal_display_layer_doc("chap-1", "架构", "Chapter body."),
        encoding="utf-8",
    )

    # No _derive-chap-2.json / _body-chap-2.txt / chapter anchor written — a
    # dropped chapter must never be checked for rendered artifacts.
    error = validate_display_layer_artifacts(
        display_layer_revision_dir,
        compose_doc,
        tmp_path,
        "lulu-design",
    )
    assert error is None
