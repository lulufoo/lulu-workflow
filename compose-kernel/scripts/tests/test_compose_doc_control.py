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
    assert compose_preamble(preamble="# Title\n", preamble_addon="addon\n").endswith("\n")


def test_init_doc_overwrites(doc_path: Path):
    init_doc(doc_path, preamble="# Plan\n\n", preamble_addon="**Outline:** test\n\n")
    text = doc_path.read_text(encoding="utf-8")
    assert text.startswith("# Plan")
    assert "**Outline:** test" in text


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
    init_doc(doc_path, preamble="# Feature\n\n", preamble_addon="addon\n\n")
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
