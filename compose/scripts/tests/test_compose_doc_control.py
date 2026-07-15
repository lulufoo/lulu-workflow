#!/usr/bin/env python3
"""Tests for compose_doc_control.py (init-doc + append-chapter only, K3-d)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compose_doc_control import (  # noqa: E402
    append_chapter,
    compose_preamble,
    init_doc,
    main,
    render_chapter_fragment,
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
