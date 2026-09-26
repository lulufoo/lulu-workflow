#!/usr/bin/env python3
"""Tests for compose_doc_control.py (init-doc + append-chapter + assemble-arc)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_WRITING = Path(__file__).resolve().parent.parent / "writing"
sys.path.insert(0, str(_WRITING))
sys.path.insert(0, str(_WRITING / "schema"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_kernel"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compose_doc_control import (  # noqa: E402
    append_chapter,
    assemble_arc_markdown,
    assemble_arc_to_path,
    compose_preamble,
    init_doc,
    main,
    render_chapter_fragment,
    render_heading,
)


@pytest.fixture
def doc_path(tmp_path: Path) -> Path:
    return tmp_path / "tech-doc.md"


def test_compose_preamble_trailing_newline():
    assert compose_preamble(preamble="# Title\n").endswith("\n")


def test_init_doc_overwrites(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n")
    text = doc_path.read_text(encoding="utf-8")
    assert text.startswith("# Plan")


def test_render_chapter_fragment_omit_default_no_heading():
    fragment = render_chapter_fragment("chap-1", "Body one.", is_first=True)
    assert fragment.startswith("<!-- chapter:chap-1 -->\nBody one.")
    assert "## " not in fragment
    assert "#### " not in fragment


def test_render_chapter_fragment_show_uses_h4():
    fragment = render_chapter_fragment(
        "chap-1",
        "Body one.",
        lens_heading="show",
        display_title="架构",
        is_first=True,
    )
    assert fragment.startswith("<!-- chapter:chap-1 -->\n#### 架构\n\nBody one.")


def test_render_chapter_fragment_not_first_has_separator():
    fragment = render_chapter_fragment(
        "chap-2",
        "Body two.",
        lens_heading="show",
        display_title="验证",
        is_first=False,
    )
    assert fragment.startswith("\n---\n\n<!-- chapter:chap-2 -->")


def test_append_chapter_omit_default(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", body="Body one.")
    raw = doc_path.read_text(encoding="utf-8")
    assert "<!-- chapter:chap-1 -->\nBody one." in raw
    assert "#### " not in raw


def test_append_chapter_show_heading(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(
        doc_path,
        cid="chap-1",
        body="Body one.",
        lens_heading="show",
        display_title="架构",
    )
    raw = doc_path.read_text(encoding="utf-8")
    assert "#### 架构" in raw
    assert "Body one." in raw


def test_append_chapter_second_gets_separator(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", body="Body one.")
    append_chapter(doc_path, cid="chap-2", body="Body two.")
    raw = doc_path.read_text(encoding="utf-8")
    assert raw.count("<!-- chapter:") == 2
    assert "---" in raw
    from chapter_doc_schema import chapter_body_by_id  # noqa: WPS433

    assert "Body one." in chapter_body_by_id(raw, "chap-1")
    assert "Body two." in chapter_body_by_id(raw, "chap-2")
    assert "Body two." not in chapter_body_by_id(raw, "chap-1")


def test_append_chapter_rejects_duplicate(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="chap-1", body="Body one.")
    with pytest.raises(ValueError, match="already present"):
        append_chapter(doc_path, cid="chap-1", body="Body again.")


def test_append_chapter_show_rejects_empty_display_title(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    with pytest.raises(ValueError, match="display_title"):
        append_chapter(
            doc_path,
            cid="chap-1",
            body="Body one.",
            lens_heading="show",
            display_title="   ",
        )
    assert "chapter:chap-1" not in doc_path.read_text(encoding="utf-8")


def test_append_chapter_rejects_empty_cid(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    with pytest.raises(ValueError, match="non-empty"):
        append_chapter(doc_path, cid="   ", body="Body one.")


def test_append_chapter_preserves_case_sensitive_id(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    append_chapter(doc_path, cid="Chap-1", body="Body one.")
    raw = doc_path.read_text(encoding="utf-8")
    assert "<!-- chapter:Chap-1 -->" in raw
    assert "<!-- chapter:chap-1 -->" not in raw


def test_append_chapter_cli_revision_dir_omit(doc_path: Path, tmp_path: Path):
    revision_dir = tmp_path / "revision1"
    revision_dir.mkdir()
    (revision_dir / "_body-chap-1.txt").write_text("Chapter body.", encoding="utf-8")
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
    assert "#### " not in raw
    from chapter_doc_schema import chapter_body_by_id  # noqa: WPS433

    assert "Chapter body." in chapter_body_by_id(raw, "chap-1")


def test_append_chapter_cli_revision_dir_show_needs_derive(doc_path: Path, tmp_path: Path):
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
            "--lens-heading",
            "show",
        ]
    )
    assert rc == 0
    assert "#### 架构" in doc_path.read_text(encoding="utf-8")


def test_append_chapter_cli_inline_omit_body_only(doc_path: Path):
    init_doc(doc_path, preamble="# Feature\n\n")
    rc = main(
        [
            "append-chapter",
            "--path",
            str(doc_path),
            "--chapter-id",
            "chap-1",
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


def test_append_chapter_cli_show_requires_display_title(doc_path: Path):
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
            "--lens-heading",
            "show",
        ]
    )
    assert rc == 1


def test_render_heading_levels():
    assert render_heading(2, "G") == "## G"
    assert render_heading(3, "L") == "### L"
    assert render_heading(9, "X") == "###### X"


def _sample_arc_with_tree() -> dict:
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "tree": {
            "id": "ROOT",
            "title": "Root package",
            "children": [
                {"id": "problem", "title": "本轮要解决什么"},
                {
                    "id": "contract",
                    "title": "Binding Contract 对外形状",
                    "children": [
                        {"id": "T1_1", "title": "Set 载荷形状"},
                    ],
                },
            ],
        },
        "leaves": [
            {
                "id": "problem",
                "title": "本轮要解决什么",
                "fact_ids": ["F-1"],
                "chapters": [{"lens": "CTX", "fact_ids": ["F-1"]}],
            },
            {
                "id": "T1_1",
                "title": "Set 载荷形状",
                "fact_ids": ["F-2", "F-3"],
                "chapters": [
                    {"lens": "ST", "fact_ids": ["F-2"]},
                    {"lens": "IF", "fact_ids": ["F-3"]},
                ],
            },
        ],
    }


def test_assemble_arc_tree_omit(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    for cid, body in [
        ("problem-CTX", "problem ctx body"),
        ("T1_1-ST", "st body"),
        ("T1_1-IF", "if body"),
    ]:
        (rev / f"_body-{cid}.txt").write_text(body + "\n", encoding="utf-8")
    text = assemble_arc_markdown(
        _sample_arc_with_tree(),
        revision_dir=rev,
        preamble="# Doc\n\n**Status:** Draft\n",
        lens_heading="omit",
        tree_mode="auto",
    )
    assert text.startswith("# Doc\n")
    assert "## 本轮要解决什么" in text
    assert "## Binding Contract 对外形状" in text
    assert "### Set 载荷形状" in text
    assert "<!-- chapter:problem-CTX -->" in text
    assert "<!-- chapter:T1_1-ST -->" in text
    assert "<!-- chapter:T1_1-IF -->" in text
    assert "· CTX" not in text
    assert "#### CTX" not in text
    assert "Root package" not in text  # root title not emitted
    # leaf under group is ###, not a top-level ## leaf title
    assert "\n## Set 载荷形状\n" not in text
    assert text.count("### Set 载荷形状") == 1


def test_assemble_arc_missing_leaf_in_tree_hard_error(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    (rev / "_body-problem-CTX.txt").write_text("x\n", encoding="utf-8")
    arc = _sample_arc_with_tree()
    arc["tree"] = {"id": "ROOT", "title": "R", "children": [{"id": "problem", "title": "P"}]}
    with pytest.raises(ValueError, match="does not cover all leaves"):
        assemble_arc_markdown(
            arc,
            revision_dir=rev,
            preamble="# Doc\n",
            tree_mode="auto",
        )


def test_assemble_arc_flat_ignore_tree(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    for cid in ("problem-CTX", "T1_1-ST", "T1_1-IF"):
        (rev / f"_body-{cid}.txt").write_text(f"{cid}\n", encoding="utf-8")
    text = assemble_arc_markdown(
        _sample_arc_with_tree(),
        revision_dir=rev,
        preamble="# Doc\n",
        tree_mode="ignore",
    )
    assert "## 本轮要解决什么" in text
    assert "## Set 载荷形状" in text
    assert "### Set 载荷形状" not in text
    assert "## Binding Contract 对外形状" not in text


def test_assemble_arc_cli(tmp_path: Path, doc_path: Path):
    from workflow_paths import seed_revision_profile_pointer  # noqa: WPS433

    rev = tmp_path / "rev"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    slice_dir = rev / "execution"
    slice_dir.mkdir(parents=True, exist_ok=True)
    arc = _sample_arc_with_tree()
    (slice_dir / "_narrative-arc.json").write_text(
        json.dumps(arc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for cid, body in [
        ("problem-CTX", "problem ctx body"),
        ("T1_1-ST", "st body"),
        ("T1_1-IF", "if body"),
    ]:
        (slice_dir / f"_body-{cid}.txt").write_text(body + "\n", encoding="utf-8")
    rc = main(
        [
            "assemble-arc",
            "--path",
            str(doc_path),
            "--revision-dir",
            str(rev),
            "--preamble",
            "# Doc\n\n",
            "--skip-write-state",
        ]
    )
    assert rc == 0
    raw = doc_path.read_text(encoding="utf-8")
    assert "## Binding Contract 对外形状" in raw
    assert "### Set 载荷形状" in raw
    result = json.loads(
        # CLI prints JSON on stdout — re-run via API for structure check
        json.dumps(assemble_arc_to_path(
            doc_path,
            revision_dir=rev,
            preamble="# Doc\n\n",
            skip_write_state=True,
        ))
    )
    assert result["ok"] is True
    assert result["leaves"] == 2
