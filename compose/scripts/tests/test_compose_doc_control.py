#!/usr/bin/env python3
"""Tests for compose_doc_control.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compose_doc_control import (  # noqa: E402
    append_intent,
    build_outline_intent_layout,
    compose_preamble,
    init_doc,
    main,
    patch_block_heading,
    render_intent_fragment,
)
from compose_doc_schema import parse_sections, section_body_by_key  # noqa: E402
from test_template_data import OUTLINE_REGISTRY_FEATURE  # noqa: E402


@pytest.fixture
def outline_path(tmp_path: Path) -> Path:
    path = tmp_path / "outline-registry.json"
    path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    return path


@pytest.fixture
def doc_path(tmp_path: Path) -> Path:
    return tmp_path / "tech-doc.md"


def test_compose_preamble_trailing_newline():
    assert compose_preamble(preamble="# Title\n").endswith("\n")


def test_init_doc_overwrites(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n")
    text = doc_path.read_text(encoding="utf-8")
    assert text.startswith("# Plan")


def test_build_outline_intent_layout_first_and_last_block():
    layout = build_outline_intent_layout(OUTLINE_REGISTRY_FEATURE)
    assert layout["CTX"]["first_in_block"] is True
    assert layout["CTX"]["last_in_block"] is False
    assert layout["GO"]["first_in_block"] is False
    assert layout["GO"]["last_in_block"] is True
    assert layout["GO"]["last_block"] is False
    assert layout["VF"]["last_in_block"] is True
    assert layout["VF"]["last_block"] is True


def test_render_intent_fragment_first_in_block():
    layout = build_outline_intent_layout(OUTLINE_REGISTRY_FEATURE)["CTX"]
    fragment = render_intent_fragment("CTX", "现状", "Body.", layout=layout)
    assert "## Overview" in fragment
    assert "### 现状 <!-- section-key:CTX -->" in fragment
    assert "Body." in fragment
    assert "---" not in fragment


def test_render_intent_fragment_last_in_block_adds_separator():
    layout = build_outline_intent_layout(OUTLINE_REGISTRY_FEATURE)["SC"]
    fragment = render_intent_fragment("SC", "范围", "Scope.", layout=layout)
    assert fragment.startswith("\n---\n")
    assert "## Boundaries" in fragment


def test_append_intent_sequence(doc_path: Path):
    outline = OUTLINE_REGISTRY_FEATURE
    init_doc(doc_path, preamble="# Feature\n\n")
    append_intent(
        doc_path,
        section_key="CTX",
        display_title="现状",
        body="Context.",
        outline=outline,
    )
    append_intent(
        doc_path,
        section_key="GO",
        display_title="目标",
        body="Goal.",
        outline=outline,
    )
    append_intent(
        doc_path,
        section_key="SC",
        display_title="范围",
        body="Scope.",
        outline=outline,
    )
    raw = doc_path.read_text(encoding="utf-8")
    assert section_body_by_key(raw, "CTX") == "Context."
    assert section_body_by_key(raw, "GO") == "Goal."
    assert section_body_by_key(raw, "SC") == "Scope."
    parsed = parse_sections(raw)
    assert parsed["CTX"]["display_heading"] == "现状"
    assert "## Overview" in raw
    assert "## Boundaries" in raw
    assert raw.index("---") < raw.index("## Boundaries")


def test_append_intent_invariants_block_after_design(doc_path: Path):
    """I maps to IV block; persists after AR/KD with its own H2 heading."""
    outline = OUTLINE_REGISTRY_FEATURE
    init_doc(doc_path, preamble="# Feature\n\n")
    for key, title, body in [
        ("CTX", "Context", "ctx"),
        ("GO", "Goal", "goal"),
        ("SC", "Scope", "scope"),
        ("NG", "Non-Goals", "ng"),
        ("AR", "Architecture", "ar"),
        ("KD", "Decisions", "kd"),
        ("I", "Invariants", "inv"),
    ]:
        append_intent(
            doc_path,
            section_key=key,
            display_title=title,
            body=body,
            outline=outline,
        )
    raw = doc_path.read_text(encoding="utf-8")
    assert raw.index("## Design") < raw.index("## Invariants")
    assert raw.index("## Invariants") < raw.index("### Invariants <!-- section-key:I -->")
    assert "## Boundaries" in raw
    assert raw.count("## Boundaries") == 1


def test_append_intent_rejects_duplicate_anchor(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n")
    outline = OUTLINE_REGISTRY_FEATURE
    append_intent(
        doc_path,
        section_key="CTX",
        display_title="现状",
        body="Body.",
        outline=outline,
    )
    with pytest.raises(ValueError, match="already present"):
        append_intent(
            doc_path,
            section_key="CTX",
            display_title="重复",
            body="Again.",
            outline=outline,
        )


def test_append_intent_unknown_section(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n")
    with pytest.raises(ValueError, match="not found in outline"):
        append_intent(
            doc_path,
            section_key="MISSING",
            display_title="x",
            body="",
            outline=OUTLINE_REGISTRY_FEATURE,
        )


def test_append_intent_revision_dir(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    (revision_dir / "_body-CTX.txt").write_text("Context.", encoding="utf-8")
    (revision_dir / "_title-display.json").write_text(
        json.dumps({"CTX": "现状"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-intent",
            "--path",
            str(doc_path),
            "--section",
            "CTX",
            "--revision-dir",
            str(revision_dir),
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 0
    raw = doc_path.read_text(encoding="utf-8")
    assert "### 现状 <!-- section-key:CTX -->" in raw
    assert section_body_by_key(raw, "CTX") == "Context."


def test_append_intent_inline_display_title(doc_path: Path, tmp_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    rc = main(
        [
            "append-intent",
            "--path",
            str(doc_path),
            "--section",
            "CTX",
            "--display-title",
            "现状",
            "--body",
            "Context.",
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 0
    raw = doc_path.read_text(encoding="utf-8")
    assert "### 现状 <!-- section-key:CTX -->" in raw
    assert section_body_by_key(raw, "CTX") == "Context."




def test_append_intent_revision_dir_rejects_invalid_display_json(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    (revision_dir / "_body-CTX.txt").write_text("Context.", encoding="utf-8")
    (revision_dir / "_title-display.json").write_text("{not json", encoding="utf-8")
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-intent",
            "--path",
            str(doc_path),
            "--section",
            "CTX",
            "--revision-dir",
            str(revision_dir),
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 1


def test_append_intent_revision_dir_mutually_exclusive_with_inline_title(
    doc_path: Path, tmp_path: Path
):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-intent",
            "--path",
            str(doc_path),
            "--section",
            "CTX",
            "--revision-dir",
            str(revision_dir),
            "--display-title",
            "现状",
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 1


def test_append_intent_requires_display_title(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n")
    rc = main(
        [
            "append-intent",
            "--path",
            str(doc_path),
            "--section",
            "CTX",
            "--body",
            "Body.",
        ]
    )
    assert rc == 1


def test_set_display_title_writes_json(tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    rc = main(
        [
            "set-display-title",
            "--revision-dir",
            str(revision_dir),
            "--section",
            "CTX",
            "--title",
            "现状",
        ]
    )
    assert rc == 0
    data = json.loads((revision_dir / "_title-display.json").read_text(encoding="utf-8"))
    assert data["CTX"] == "现状"


def test_patch_block_heading_replaces_si_placeholder(doc_path: Path):
    outline = OUTLINE_REGISTRY_FEATURE
    init_doc(doc_path, preamble="# Feature\n\n")
    append_intent(
        doc_path,
        section_key="CTX",
        display_title="现状",
        body="Context.",
        outline=outline,
    )
    append_intent(
        doc_path,
        section_key="GO",
        display_title="目标",
        body="Goal.",
        outline=outline,
    )
    patch_block_heading(
        doc_path,
        block_key="OV",
        title="1. 问题与目标",
        outline=outline,
    )
    raw = doc_path.read_text(encoding="utf-8")
    assert "## 1. 问题与目标" in raw
    assert "## Overview" not in raw
    assert "### 现状 <!-- section-key:CTX -->" in raw
    assert "### 目标 <!-- section-key:GO -->" in raw


def test_patch_block_heading_cli(doc_path: Path, tmp_path: Path):
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    init_doc(doc_path, preamble="# Feature\n\n")
    append_intent(
        doc_path,
        section_key="CTX",
        display_title="现状",
        body="Context.",
        outline=OUTLINE_REGISTRY_FEATURE,
    )
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    (revision_dir / "_title-block.json").write_text(
        json.dumps({"OV": "1. 问题与目标"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rc = main(
        [
            "patch-block-heading",
            "--path",
            str(doc_path),
            "--block-key",
            "OV",
            "--revision-dir",
            str(revision_dir),
            "--outline-path",
            str(outline_path),
        ]
    )
    assert rc == 0
    assert "## 1. 问题与目标" in doc_path.read_text(encoding="utf-8")


def test_patch_block_heading_fails_when_placeholder_missing(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    with pytest.raises(ValueError, match="placeholder heading not found"):
        patch_block_heading(
            doc_path,
            block_key="OV",
            title="1. 问题与目标",
            outline=OUTLINE_REGISTRY_FEATURE,
        )
