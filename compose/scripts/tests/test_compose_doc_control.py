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
    append_chapter,
    append_intent,
    build_outline_intent_layout,
    compose_preamble,
    init_doc,
    main,
    patch_block_heading,
    render_chapter_fragment,
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
    (revision_dir / "_derive-CTX.json").write_text(
        json.dumps({"section_key": "CTX", "display_title": "现状"}, ensure_ascii=False) + "\n",
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
    # _title-display.json is written by append-intent as a projection of derive
    projection = json.loads((revision_dir / "_title-display.json").read_text(encoding="utf-8"))
    assert projection["CTX"] == "现状"


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




def test_append_intent_revision_dir_rejects_invalid_derive_json(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    outline_path = tmp_path / "outline-registry.json"
    outline_path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    (revision_dir / "_body-CTX.txt").write_text("Context.", encoding="utf-8")
    (revision_dir / "_derive-CTX.json").write_text("{not json", encoding="utf-8")
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


# --- append-chapter (fact-first display layer, M4a) ---


def test_render_chapter_fragment_first_no_separator():
    fragment = render_chapter_fragment("chap-1", "架构", "Body one.", is_first=True)
    assert fragment.startswith("<!-- chapter:chap-1 -->\n## 架构\n\nBody one.")
    assert "---" not in fragment


def test_render_chapter_fragment_not_first_has_separator():
    fragment = render_chapter_fragment("chap-2", "验证", "Body two.", is_first=False)
    assert fragment.startswith("\n---\n\n<!-- chapter:chap-2 -->")


def test_append_chapter_inline(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", display_title="架构", body="Body one.")
    raw = doc_path.read_text(encoding="utf-8")
    assert "<!-- chapter:chap-1 -->" in raw
    assert "## 架构" in raw
    assert "Body one." in raw


def test_append_chapter_second_gets_separator(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", display_title="架构", body="Body one.")
    append_chapter(doc_path, cid="chap-2", display_title="验证", body="Body two.")
    raw = doc_path.read_text(encoding="utf-8")
    assert raw.count("<!-- chapter:") == 2
    assert "---" in raw
    from chapter_doc_schema import chapter_body_by_id  # noqa: WPS433

    assert "Body one." in chapter_body_by_id(raw, "chap-1")
    assert "Body two." in chapter_body_by_id(raw, "chap-2")
    assert "Body two." not in chapter_body_by_id(raw, "chap-1")


def test_append_chapter_rejects_duplicate(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", display_title="架构", body="Body one.")
    with pytest.raises(ValueError, match="already present"):
        append_chapter(doc_path, cid="chap-1", display_title="架构again", body="Body again.")


def test_append_chapter_rejects_empty_display_title(doc_path: Path):
    """Round-2 Grok review N2: append_chapter itself (not just the CLI) must
    reject an empty/whitespace display_title, so any direct Python caller
    gets the same guarantee as the CLI (render_chapter_fragment's （待补）
    fallback stays a lower-level defensive default only)."""
    init_doc(doc_path, preamble="# Feature\n\n")
    with pytest.raises(ValueError, match="display_title"):
        append_chapter(doc_path, cid="chap-1", display_title="   ", body="Body one.")
    assert "chapter:chap-1" not in doc_path.read_text(encoding="utf-8")


def test_append_chapter_rejects_empty_cid(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    with pytest.raises(ValueError, match="non-empty"):
        append_chapter(doc_path, cid="   ", display_title="架构", body="Body one.")


def test_append_chapter_preserves_case_sensitive_id(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="Chap-1", display_title="架构", body="Body one.")
    raw = doc_path.read_text(encoding="utf-8")
    assert "<!-- chapter:Chap-1 -->" in raw
    assert "<!-- chapter:chap-1 -->" not in raw


def test_append_chapter_cli_revision_dir(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    (revision_dir / "_body-chap-1.txt").write_text("Chapter body.", encoding="utf-8")
    (revision_dir / "_derive-chap-1.json").write_text(
        json.dumps({"display_title": "架构"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--revision-dir",
            str(revision_dir),
        ]
    )
    assert rc == 0
    raw = doc_path.read_text(encoding="utf-8")
    assert "<!-- chapter:chap-1 -->" in raw
    assert "## 架构" in raw
    from chapter_doc_schema import chapter_body_by_id  # noqa: WPS433

    assert "Chapter body." in chapter_body_by_id(raw, "chap-1")


def test_append_chapter_cli_inline(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--display-title",
            "架构",
            "--body",
            "Body inline.",
        ]
    )
    assert rc == 0
    assert "Body inline." in doc_path.read_text(encoding="utf-8")


def test_append_chapter_cli_rejects_mixed_revision_and_inline(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--revision-dir",
            str(revision_dir),
            "--display-title",
            "架构",
        ]
    )
    assert rc == 1


def test_append_chapter_cli_missing_body_artifact(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--revision-dir",
            str(revision_dir),
        ]
    )
    assert rc == 1


def test_append_chapter_cli_requires_display_title_or_revision_dir(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--body",
            "Body.",
        ]
    )
    assert rc == 1


def test_append_chapter_cli_rejects_empty_inline_display_title(doc_path: Path):
    """Round-1 Grok review m6: inline path must reject an empty/whitespace
    --display-title the same way the --revision-dir path rejects a missing
    display_title — never write a （待补）placeholder into the doc via the
    inline arg path."""
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
            "--display-title",
            "   ",
            "--body",
            "Body.",
        ]
    )
    assert rc == 1
    assert "chapter:chap-1" not in doc_path.read_text(encoding="utf-8")
