#!/usr/bin/env python3
"""Static landing checks for G2 topic model (archive-20.0)."""

from __future__ import annotations

from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_GATE = _COMPOSE / "inductive-runner" / "gates" / "g2-topic-loop.md"
_REF = _COMPOSE / "inductive-runner" / "references" / "g2-topic-model.md"
_SPINE = _COMPOSE / "inductive-runner" / "SKILL.md"
_OLD_REF = _COMPOSE / "inductive-runner" / "references" / "topic-cognition-model.md"


def test_g2_topic_model_reference_exists_and_names_tools():
    assert _REF.is_file()
    assert not _OLD_REF.exists()
    text = _REF.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "## Topic" in text
    assert "`gap`" in text
    assert "adopted" in text
    assert "concluded" in text
    assert "Grain" in text
    assert "gap-landscape" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_g2_gate_declares_tools_and_points_at_reference():
    text = _GATE.read_text(encoding="utf-8")
    assert "`topic-landscape`" in text
    assert "`topic-portrait`" in text
    assert "g2-topic-model.md" in text
    assert "topic_exit" in text
    assert "pre-adopt" in text or "pre-adopt clarify" in text.lower() or "clarify (pre-adopt)" in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text
    assert "docs/" not in text
    assert "archive-" not in text


def test_inductive_spine_mentions_g2_topic_model_tools():
    text = _SPINE.read_text(encoding="utf-8")
    assert "topic-landscape" in text
    assert "topic-portrait" in text
    assert "g2-topic-model.md" in text
    assert "topic_exit" in text
    assert "gap-landscape" not in text
    assert "topic-cognition-model.md" not in text
